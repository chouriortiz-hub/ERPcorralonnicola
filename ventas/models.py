"""
Módulo VENTAS
-------------
Lo usan los vendedores de mostrador para:
  - Emitir PRESUPUESTOS (no impactan stock ni facturación; son una cotización).
  - Convertir un presupuesto en PEDIDO, o cargar un pedido directo.
  - Confirmar el PEDIDO: acá es donde, línea por línea, se descuenta stock
    SOLO si `producto.descuenta_stock` es True (pedido explícito del
    usuario). El resto de las líneas quedan registradas igual (para poder
    facturarlas) pero sin tocar inventario.

Interconexión:
  - ventas -> stock: al confirmar el pedido (registrar_movimiento).
  - ventas -> facturacion: un pedido confirmado puede facturarse.
  - ventas -> repartos: un pedido puede asignarse a un reparto del día.
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
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'Pedido #{self.pk} - {self.cliente}'

    @property
    def total(self):
        return sum((l.subtotal for l in self.lineas.all()), start=0)

    @transaction.atomic
    def confirmar(self, usuario):
        """
        Descuenta stock SOLO de las líneas cuyo producto tiene
        descuenta_stock=True. El resto queda facturable pero no
        controlado por inventario (ej: flete, mano de obra, encargues).
        """
        if self.estado != self.PENDIENTE:
            raise ValidationError('Solo se pueden confirmar pedidos en estado Pendiente.')

        lineas = self.lineas.select_related('producto')
        if not lineas.exists():
            raise ValidationError('El pedido no tiene líneas cargadas.')

        for linea in lineas:
            if linea.producto.descuenta_stock:
                registrar_movimiento(
                    producto=linea.producto,
                    cantidad=linea.cantidad,
                    tipo=MovimientoStock.SALIDA,
                    origen=MovimientoStock.ORIGEN_PEDIDO,
                    usuario=usuario,
                    referencia_id=self.pk,
                    motivo=f'Pedido #{self.pk} - {self.cliente}',
                )

        self.estado = self.CONFIRMADO
        self.save(update_fields=['estado'])
        return self


class PedidoLinea(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='lineas_pedido')
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f'{self.producto.codigo} x {self.cantidad}'
