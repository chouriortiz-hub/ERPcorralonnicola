"""
Módulo REPARTOS
----------------
Permite organizar qué pedidos salen de reparto en el día, con qué chofer
y en qué vehículo, y hacer el seguimiento de la entrega.

Interconexión: solo se pueden asignar a un Reparto los Pedidos que están
CONFIRMADOS (con stock ya descontado) y cuyo `tipo_entrega` es REPARTO.
Al marcar la entrega como realizada, el pedido pasa a estado ENTREGADO.
"""
from django.core.exceptions import ValidationError
from django.db import models

from core.models import User
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
        if RepartoPedido.objects.filter(pedido=pedido).exclude(reparto=self).exists():
            raise ValidationError('Este pedido ya está asignado a otro reparto.')

        orden = orden or (self.pedidos.count() + 1)
        return RepartoPedido.objects.create(
            reparto=self, pedido=pedido, orden=orden,
            direccion_entrega=pedido.direccion_entrega,
        )


class RepartoPedido(models.Model):
    PENDIENTE = 'PENDIENTE'
    ENTREGADO = 'ENTREGADO'
    NO_ENTREGADO = 'NO_ENTREGADO'
    ESTADO_ENTREGA_CHOICES = [
        (PENDIENTE, 'Pendiente'),
        (ENTREGADO, 'Entregado'),
        (NO_ENTREGADO, 'No entregado'),
    ]

    reparto = models.ForeignKey(Reparto, on_delete=models.CASCADE, related_name='pedidos')
    pedido = models.OneToOneField(Pedido, on_delete=models.PROTECT, related_name='reparto_asignado')
    orden = models.PositiveIntegerField(default=1)
    direccion_entrega = models.CharField(max_length=250, blank=True)
    estado_entrega = models.CharField(max_length=15, choices=ESTADO_ENTREGA_CHOICES, default=PENDIENTE)
    observaciones_entrega = models.TextField(blank=True)

    class Meta:
        ordering = ['orden']

    def marcar_entregado(self):
        self.estado_entrega = self.ENTREGADO
        self.save(update_fields=['estado_entrega'])
        self.pedido.estado = Pedido.ENTREGADO
        self.pedido.save(update_fields=['estado'])

    def marcar_no_entregado(self, motivo=''):
        self.estado_entrega = self.NO_ENTREGADO
        self.observaciones_entrega = motivo
        self.save(update_fields=['estado_entrega', 'observaciones_entrega'])

    def __str__(self):
        return f'{self.reparto} -> Pedido #{self.pedido_id}'
