"""
Módulo COMUNICADOS
-------------------
Avisos que el Administrador publica para los vendedores (ofertas,
prioridades de venta, informativos). Es puramente informativo/visual:
no descuenta ni reserva stock, no interviene en `Pedido.confirmar()`.
"""
from django.db import models
from django.utils import timezone

from core.models import User


class AvisoQuerySet(models.QuerySet):
    def vigentes(self):
        ahora = timezone.now()
        return self.filter(activo=True).filter(
            models.Q(fecha_vencimiento__isnull=True) | models.Q(fecha_vencimiento__gte=ahora)
        )


class Aviso(models.Model):
    OFERTA = 'OFERTA'
    PRIORIDAD_VENTA = 'PRIORIDAD_VENTA'
    INFORMATIVO = 'INFORMATIVO'
    TIPO_CHOICES = [
        (OFERTA, 'Oferta'),
        (PRIORIDAD_VENTA, 'Prioridad de venta'),
        (INFORMATIVO, 'Informativo'),
    ]

    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=INFORMATIVO)
    productos = models.ManyToManyField('stock.Producto', blank=True, related_name='avisos')
    fecha_vencimiento = models.DateTimeField(
        null=True, blank=True,
        help_text='Dejar en blanco si el aviso no vence automáticamente.',
    )
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='avisos_creados')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    objects = AvisoQuerySet.as_manager()

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.titulo

    @property
    def vigente(self):
        if not self.activo:
            return False
        if self.fecha_vencimiento and self.fecha_vencimiento < timezone.now():
            return False
        return True
