"""
Módulo VENTAS
-------------
Lo usan los vendedores de mostrador para:
  - Emitir PRESUPUESTOS (no impactan stock ni facturación; son una cotización).
  - Convertir un presupuesto en PEDIDO, o cargar un pedido directo.
  - Confirmar el PEDIDO: acá es donde, línea por línea, se descuenta stock
    SOLO si `producto.descuenta_stock` es True (pedido explícito del
    usuario) Y la línea se retira en el momento (`sale_con_reparto=False`).
    Las líneas que salen con reparto quedan registradas igual (para poder
    facturarlas) pero sin tocar inventario todavía: su stock se descuenta
    recién cuando el reparto que las lleva marca su salida del depósito
    (ver `repartos.models.Reparto.marcar_salida`).

Interconexión:
  - ventas -> stock: al confirmar el pedido (registrar_movimiento), solo
    para las líneas que se retiran en el momento.
  - ventas -> facturacion: un pedido confirmado puede facturarse.
  - ventas -> repartos: un pedido con líneas `sale_con_reparto=True`
    pendientes puede asignarse a un reparto del día.
"""
from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.models import User
from stock.models import MovimientoStock, Producto, registrar_movimiento


class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    cuit_dni = models.CharField(max_length=20, blank=True, null=True)
    condicion_iva = models.CharField(
        max_length=30,
        choices=[
            ('CONSUMIDOR_FINAL', 'Consumidor Final'),
            ('RESPONSABLE_INSCRIPTO', 'Responsable Inscripto'),
            ('MONOTRIBUTO', 'Monotributo'),
            ('EXENTO', 'Exento'),
        ],
        default='CONSUMIDOR_FINAL',
    )
    direccion = models.CharField(max_length=250, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Presupuesto(models.Model):
    BORRADOR = 'BORRADOR'
    ENVIADO = 'ENVIADO'
    CONVERTIDO = 'CONVERTIDO'
    VENCIDO = 'VENCIDO'
    ESTADO_CHOICES = [
        (BORRADOR, 'Borrador'),
        (ENVIADO, 'Enviado al cliente'),
        (CONVERTIDO, 'Convertido a pedido'),
        (VENCIDO, 'Vencido'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='presupuestos')
    vendedor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='presupuestos_emitidos')
    fecha = models.DateTimeField(auto_now_add=True)
    validez_dias = models.PositiveIntegerField(default=7)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=BORRADOR)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'Presupuesto #{self.pk} - {self.cliente}'

    @property
    def total(self):
        return sum((l.subtotal for l in self.lineas.all()), start=0)

    @transaction.atomic
    def convertir_a_pedido(self, usuario):
        if self.estado == self.CONVERTIDO:
            raise ValidationError('Este presupuesto ya fue convertido a pedido.')

        pedido = Pedido.objects.create(
            cliente=self.cliente,
            vendedor=usuario,
            presupuesto_origen=self,
        )
        for linea in self.lineas.all():
            PedidoLinea.objects.create(
                pedido=pedido,
                producto=linea.producto,
                cantidad=linea.cantidad,
                precio_unitario=linea.precio_unitario,
            )
        self.estado = self.CONVERTIDO
        self.save(update_fields=['estado'])
        return pedido


class PresupuestoLinea(models.Model):
    presupuesto = models.ForeignKey(Presupuesto, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


class Pedido(models.Model):
    PENDIENTE = 'PENDIENTE'
    CONFIRMADO = 'CONFIRMADO'
    FACTURADO = 'FACTURADO'
    ENTREGADO = 'ENTREGADO'
    CANCELADO = 'CANCELADO'
    ESTADO_CHOICES = [
        (PENDIENTE, 'Pendiente'),
        (CONFIRMADO, 'Confirmado (impactó stock)'),
        (FACTURADO, 'Facturado'),
        (ENTREGADO, 'Entregado'),
        (CANCELADO, 'Cancelado'),
    ]

    ENTREGA_MOSTRADOR = 'MOSTRADOR'
    ENTREGA_REPARTO = 'REPARTO'
    TIPO_ENTREGA_CHOICES = [
        (ENTREGA_MOSTRADOR, 'Retira por mostrador'),
        (ENTREGA_REPARTO, 'Reparto a domicilio'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='pedidos')
    vendedor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pedidos_emitidos')
    presupuesto_origen = models.ForeignKey(
        Presupuesto, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=PENDIENTE)
    tipo_entrega = models.CharField(max_length=10, choices=TIPO_ENTREGA_CHOICES, default=ENTREGA_MOSTRADOR)
    direccion_entrega = models.CharField(max_length=250, blank=True)
    fecha_entrega_estimada = models.DateField(
        null=True, blank=True,
        help_text='Día estimado de entrega para las líneas que salen con reparto.',
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'Pedido #{self.pk} - {self.cliente}'

    @property
    def total(self):
        return sum((l.subtotal for l in self.lineas.all()), start=0)

    @property
    def lineas_pendientes_reparto(self):
        """
        Líneas marcadas para salir con reparto cuyo stock todavía no se
        descontó (recién se descuenta cuando el RepartoPedido que las lleva
        marca su salida del depósito, ver RepartoPedido.marcar_salida).
        """
        return self.lineas.select_related('producto').filter(
            sale_con_reparto=True, stock_descontado=False, producto__descuenta_stock=True,
        )

    @property
    def tiene_lineas_pendientes_reparto(self):
        return self.lineas_pendientes_reparto.exists()

    def actualizar_tipo_entrega(self):
        """
        Infiere tipo_entrega a partir de las líneas cargadas: si al menos una
        línea sale con reparto, todo el pedido se gestiona como entrega a
        domicilio (define a qué Repartos puede asignarse), aunque el resto
        de las líneas se retiren por mostrador en el momento.
        """
        tiene_reparto = self.lineas.filter(sale_con_reparto=True).exists()
        nuevo_tipo = self.ENTREGA_REPARTO if tiene_reparto else self.ENTREGA_MOSTRADOR
        if nuevo_tipo != self.tipo_entrega:
            self.tipo_entrega = nuevo_tipo
            self.save(update_fields=['tipo_entrega'])

    @transaction.atomic
    def confirmar(self, usuario):
        """
        Descuenta stock SOLO de las líneas cuyo producto tiene
        descuenta_stock=True Y que se retiran en el momento (sale_con_reparto
        es False). Las líneas que salen con reparto quedan facturables pero
        pendientes: su stock se descuenta recién cuando el reparto que las
        lleva marca su salida del depósito (Reparto.marcar_salida), no acá.
        """
        if self.estado != self.PENDIENTE:
            raise ValidationError('Solo se pueden confirmar pedidos en estado Pendiente.')

        lineas = self.lineas.select_related('producto')
        if not lineas.exists():
            raise ValidationError('El pedido no tiene líneas cargadas.')

        for linea in lineas:
            if linea.producto.descuenta_stock and not linea.sale_con_reparto:
                registrar_movimiento(
                    producto=linea.producto,
                    cantidad=linea.cantidad,
                    tipo=MovimientoStock.SALIDA,
                    origen=MovimientoStock.ORIGEN_PEDIDO,
                    usuario=usuario,
                    referencia_id=self.pk,
                    motivo=f'Pedido #{self.pk} - {self.cliente}',
                )
                linea.stock_descontado = True
                linea.save(update_fields=['stock_descontado'])

        self.estado = self.CONFIRMADO
        self.save(update_fields=['estado'])
        return self


class PedidoLinea(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='lineas_pedido')
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    sale_con_reparto = models.BooleanField(
        default=False,
        help_text='Si está activo, esta línea no se retira por mostrador: sale con el reparto y su stock se descuenta recién cuando el reparto marca su salida.',
    )
    stock_descontado = models.BooleanField(
        default=False,
        help_text='Gestionado por el sistema: indica si esta línea ya impactó el stock (al confirmar el pedido, o al salir el reparto).',
    )

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f'{self.producto.codigo} x {self.cantidad}'
