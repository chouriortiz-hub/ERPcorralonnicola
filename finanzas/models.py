"""
Módulo FINANZAS (bonus, sugerido a partir de la sección 8 de la guía)
----------------------------------------------------------------------
Libro Diario con asientos automáticos: cada vez que se AUTORIZA una
factura o se CONFIRMA una compra, el sistema genera el asiento contable
correspondiente sin intervención manual. Cierra el círculo del ERP:
Stock <-> Ventas/Compras <-> Facturación <-> Finanzas.

CierreCaja: control de caja física de mostrador, independiente del Libro
Diario contable. Cada vendedor abre su caja con un fondo inicial y, al
finalizar el turno, cuenta el efectivo real; el sistema calcula lo
esperado a partir de sus propios pedidos cargados en ese lapso y expone
la diferencia (sobrante/faltante) para que quede un registro por turno.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from core.models import User


class CuentaContable(models.TextChoices):
    INVENTARIO = '1000', 'Inventario / Mercadería'
    BANCO_CAJA = '1001', 'Banco / Caja'
    VENTAS = '4000', 'Ventas'
    IVA_DEBITO_FISCAL = '2100', 'IVA Débito Fiscal'
    PROVEEDORES = '2000', 'Proveedores (a pagar)'
    CLIENTES = '1100', 'Clientes (a cobrar)'


class Journal(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    cuenta_codigo = models.CharField(max_length=10, choices=CuentaContable.choices)
    debe = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    haber = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    referencia_tipo = models.CharField(max_length=20)  # 'FACTURA' | 'COMPRA'
    referencia_id = models.PositiveIntegerField()
    descripcion = models.CharField(max_length=250, blank=True)

    class Meta:
        verbose_name_plural = 'Libro Diario'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.cuenta_codigo} D:{self.debe} H:{self.haber} ({self.referencia_tipo} #{self.referencia_id})'


class CierreCaja(models.Model):
    ABIERTA = 'ABIERTA'
    CERRADA = 'CERRADA'
    ESTADO_CHOICES = [
        (ABIERTA, 'Abierta'),
        (CERRADA, 'Cerrada'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cierres_caja')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default=ABIERTA)

    fecha_apertura = models.DateTimeField(auto_now_add=True)
    monto_apertura = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    fecha_cierre = models.DateTimeField(null=True, blank=True)
    efectivo_contado = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_ventas_sistema = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Cierre de caja'
        verbose_name_plural = 'Cierres de caja'
        ordering = ['-fecha_apertura']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario'], condition=models.Q(estado='ABIERTA'),
                name='una_caja_abierta_por_usuario',
            ),
        ]

    def __str__(self):
        return f'Caja {self.usuario} - {self.fecha_apertura:%d/%m/%Y %H:%M}'

    @property
    def diferencia(self):
        """Efectivo contado vs. lo esperado (fondo inicial + ventas del turno). Positivo = sobrante, negativo = faltante."""
        if self.efectivo_contado is None or self.total_ventas_sistema is None:
            return None
        return self.efectivo_contado - (self.monto_apertura + self.total_ventas_sistema)

    def calcular_ventas_periodo(self, hasta=None):
        """Suma el total de los pedidos que este vendedor cargó mientras la caja estuvo abierta (excluye cancelados)."""
        from ventas.models import Pedido

        fin = hasta or timezone.now()
        pedidos = (
            Pedido.objects
            .filter(vendedor=self.usuario, fecha__gte=self.fecha_apertura, fecha__lte=fin)
            .exclude(estado=Pedido.CANCELADO)
            .prefetch_related('lineas')
        )
        return sum((p.total for p in pedidos), start=Decimal('0'))

    @transaction.atomic
    def cerrar(self, efectivo_contado, observaciones=''):
        if self.estado == self.CERRADA:
            raise ValidationError('Esta caja ya está cerrada.')

        self.fecha_cierre = timezone.now()
        self.total_ventas_sistema = self.calcular_ventas_periodo(hasta=self.fecha_cierre)
        self.efectivo_contado = efectivo_contado
        self.estado = self.CERRADA
        if observaciones:
            self.observaciones = observaciones
        self.save(update_fields=[
            'fecha_cierre', 'total_ventas_sistema', 'efectivo_contado', 'estado', 'observaciones',
        ])
        return self
