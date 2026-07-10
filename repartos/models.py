"""
Módulo REPARTOS
----------------
Permite organizar qué pedidos salen de reparto en el día, con qué chofer
y en qué vehículo, y hacer el seguimiento de la entrega.

Interconexión: solo se pueden asignar a un Reparto los Pedidos que están
CONFIRMADOS o FACTURADOS y que tienen líneas pendientes de reparto
(`tiene_lineas_pendientes_reparto`). El stock de esas líneas NO se
descuenta al confirmar el pedido ni al asignarlo al reparto: se descuenta
recién cuando ESE PEDIDO puntual registra su salida del depósito
(`RepartoPedido.registrar_salida`), de a poco y solo por lo que
efectivamente sale (no hace falta que salga todo junto). Si no sale la
cantidad completa de una línea, el saldo queda pendiente
(`PedidoLinea.cantidad_pendiente`) y el pedido puede volver a asignarse a
OTRO reparto (un pedido puede tener más de un `RepartoPedido` a lo largo
de su vida, uno por cada intento de reparto). Al registrar la primera
salida del reparto, este pasa de PROGRAMADO a EN_CURSO. El pedido pasa a
ENTREGADO recién cuando ya no le queda ninguna línea de reparto pendiente.
"""
from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.models import User
from stock.models import MovimientoStock, registrar_movimiento
from ventas.models import Pedido


class Vehiculo(models.Model):
    patente = models.CharField(max_length=15, unique=True)
    descripcion = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.patente} ({self.descripcion})' if self.descripcion else self.patente


class Reparto(models.Model):
    PROGRAMADO = 'PROGRAMADO'
    EN_CURSO = 'EN_CURSO'
    FINALIZADO = 'FINALIZADO'
    ESTADO_CHOICES = [
        (PROGRAMADO, 'Programado'),
        (EN_CURSO, 'En curso'),
        (FINALIZADO, 'Finalizado'),
    ]

    fecha = models.DateField()
    chofer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='repartos_asignados')
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.PROTECT, related_name='repartos')
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=PROGRAMADO)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'Reparto {self.fecha} - {self.chofer} ({self.vehiculo})'

    def agregar_pedido(self, pedido, orden=None):
        if pedido.estado not in (Pedido.CONFIRMADO, Pedido.FACTURADO):
            raise ValidationError('Solo se pueden repartir pedidos Confirmados o Facturados.')
        if pedido.tipo_entrega != Pedido.ENTREGA_REPARTO:
            raise ValidationError('Este pedido no está marcado como Reparto a domicilio.')
        if not pedido.tiene_lineas_pendientes_reparto:
            raise ValidationError('Este pedido no tiene líneas pendientes de reparto.')
        if RepartoPedido.objects.filter(pedido=pedido, reparto=self).exists():
            raise ValidationError('Este pedido ya está en este reparto.')
        if RepartoPedido.objects.filter(pedido=pedido, estado_salida=RepartoPedido.PENDIENTE).exclude(reparto=self).exists():
            raise ValidationError('Este pedido ya está asignado a otro reparto pendiente de salida.')

        orden = orden or (self.pedidos.count() + 1)
        return RepartoPedido.objects.create(
            reparto=self, pedido=pedido, orden=orden,
            direccion_entrega=pedido.direccion_entrega,
        )

    @transaction.atomic
    def marcar_salida(self, usuario):
        """
        Marca la salida COMPLETA de TODOS los pedidos todavía pendientes del
        reparto de una sola vez (delega en `RepartoPedido.marcar_salida`
        para cada uno). Pasa el reparto a EN_CURSO si todavía estaba
        Programado.
        """
        if self.estado == self.FINALIZADO:
            raise ValidationError('Este reparto ya está finalizado.')

        pendientes = self.pedidos.filter(estado_salida=RepartoPedido.PENDIENTE).select_related('pedido')
        if not pendientes.exists():
            raise ValidationError('No hay pedidos pendientes de salida en este reparto.')
        for reparto_pedido in pendientes:
            reparto_pedido.marcar_salida(usuario)

        if self.estado == self.PROGRAMADO:
            self.estado = self.EN_CURSO
            self.save(update_fields=['estado'])
        return self


class RepartoPedido(models.Model):
    PENDIENTE = 'PENDIENTE'
    ENTREGADO = 'ENTREGADO'
    NO_ENTREGADO = 'NO_ENTREGADO'
    ESTADO_ENTREGA_CHOICES = [
        (PENDIENTE, 'Pendiente'),
        (ENTREGADO, 'Entregado'),
        (NO_ENTREGADO, 'No entregado'),
    ]

    SALIO = 'SALIO'
    PARCIAL = 'PARCIAL'
    NO_SALIO = 'NO_SALIO'
    ESTADO_SALIDA_CHOICES = [
        (PENDIENTE, 'Pendiente'),
        (PARCIAL, 'Salida parcial'),
        (SALIO, 'Salió completo'),
        (NO_SALIO, 'No salió'),
    ]

    reparto = models.ForeignKey(Reparto, on_delete=models.CASCADE, related_name='pedidos')
    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, related_name='repartos_asignados')
    orden = models.PositiveIntegerField(default=1)
    direccion_entrega = models.CharField(max_length=250, blank=True)
    estado_salida = models.CharField(max_length=15, choices=ESTADO_SALIDA_CHOICES, default=PENDIENTE)
    motivo_no_salida = models.TextField(blank=True)
    estado_entrega = models.CharField(max_length=15, choices=ESTADO_ENTREGA_CHOICES, default=PENDIENTE)
    observaciones_entrega = models.TextField(blank=True)

    class Meta:
        ordering = ['orden']

    @transaction.atomic
    def registrar_salida(self, usuario, cantidades):
        """
        Registra cuánto sale AHORA de cada línea pendiente de reparto de
        este pedido. `cantidades` es un dict {pedido_linea_id: Decimal} con
        lo que efectivamente sale del depósito (puede ser menor a lo
        pendiente de cada línea). El stock se descuenta solo por esa
        cantidad. Si al terminar todavía queda saldo pendiente en alguna
        línea, este RepartoPedido queda en PARCIAL (el saldo se puede
        asignar a otro reparto); si no queda nada pendiente, queda en SALIO.
        """
        if self.estado_salida not in (self.PENDIENTE, self.PARCIAL):
            raise ValidationError('Este pedido ya fue marcado como salido o no salido.')

        lineas_pendientes = {l.pk: l for l in self.pedido.lineas_pendientes_reparto}
        if not lineas_pendientes:
            raise ValidationError('Este pedido no tiene líneas pendientes de reparto.')

        hubo_movimiento = False
        for linea_id, cantidad_solicitada in cantidades.items():
            linea = lineas_pendientes.get(linea_id)
            if linea is None or not cantidad_solicitada:
                continue
            pendiente = linea.cantidad_pendiente
            if cantidad_solicitada < 0 or cantidad_solicitada > pendiente:
                raise ValidationError(
                    f'La cantidad para "{linea.producto.nombre}" debe estar entre 0 y {pendiente}.'
                )
            registrar_movimiento(
                producto=linea.producto,
                cantidad=cantidad_solicitada,
                tipo=MovimientoStock.SALIDA,
                origen=MovimientoStock.ORIGEN_PEDIDO,
                usuario=usuario,
                referencia_id=self.pedido_id,
                motivo=f'Salida a reparto #{self.reparto_id} - Pedido #{self.pedido_id}',
            )
            linea.cantidad_salida += cantidad_solicitada
            linea.save(update_fields=['cantidad_salida'])
            hubo_movimiento = True

        if not hubo_movimiento:
            raise ValidationError('No se cargó ninguna cantidad de salida.')

        self.estado_salida = self.PARCIAL if self.pedido.tiene_lineas_pendientes_reparto else self.SALIO
        self.save(update_fields=['estado_salida'])

        if self.reparto.estado == Reparto.PROGRAMADO:
            self.reparto.estado = Reparto.EN_CURSO
            self.reparto.save(update_fields=['estado'])
        return self

    def marcar_salida(self, usuario):
        """Atajo: registra la salida COMPLETA de todo lo pendiente de este pedido."""
        cantidades = {l.pk: l.cantidad_pendiente for l in self.pedido.lineas_pendientes_reparto}
        return self.registrar_salida(usuario, cantidades)

    def marcar_no_salio(self, motivo=''):
        if self.estado_salida != self.PENDIENTE:
            raise ValidationError('Este pedido ya fue marcado como salido o no salido.')
        self.estado_salida = self.NO_SALIO
        self.motivo_no_salida = motivo
        self.save(update_fields=['estado_salida', 'motivo_no_salida'])
        return self

    def marcar_entregado(self):
        if self.estado_salida not in (self.SALIO, self.PARCIAL):
            raise ValidationError(
                'Este pedido todavía no salió del depósito '
                '(no se puede entregar mercadería que no salió).'
            )
        self.estado_entrega = self.ENTREGADO
        self.save(update_fields=['estado_entrega'])
        if not self.pedido.tiene_lineas_pendientes_reparto:
            self.pedido.estado = Pedido.ENTREGADO
            self.pedido.save(update_fields=['estado'])

    def marcar_no_entregado(self, motivo=''):
        self.estado_entrega = self.NO_ENTREGADO
        self.observaciones_entrega = motivo
        self.save(update_fields=['estado_entrega', 'observaciones_entrega'])

    def __str__(self):
        return f'{self.reparto} -> Pedido #{self.pedido_id}'
