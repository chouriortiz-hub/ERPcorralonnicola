"""
Módulo COMPRAS
--------------
Carga de compras a proveedores. Al CONFIRMAR una compra, cada línea:
  1) Actualiza el PMP del producto (stock.update_pmp).
  2) Genera una ENTRADA de stock (stock.registrar_movimiento).
Todo dentro de una transacción atómica (patrón de la guía técnica,
sección 6): si falla una línea, se revierte toda la compra.

Nota: a diferencia de VENTAS, en COMPRAS el stock SIEMPRE se actualiza
(no depende del flag `descuenta_stock`, que es exclusivo del circuito de
venta/salida).
"""
from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.models import User
from stock.models import MovimientoStock, Producto, Proveedor, registrar_movimiento, update_pmp


class Compra(models.Model):
    BORRADOR = 'BORRADOR'
    CONFIRMADA = 'CONFIRMADA'
    ANULADA = 'ANULADA'
    ESTADO_CHOICES = [
        (BORRADOR, 'Borrador'),
        (CONFIRMADA, 'Confirmada (impactó stock)'),
        (ANULADA, 'Anulada'),
    ]

    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='compras')
    numero_comprobante = models.CharField(max_length=50, blank=True)
    fecha = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=BORRADOR)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='compras_cargadas')
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']

    def __str__(self):
        return f'Compra #{self.pk} - {self.proveedor}'

    @property
    def total(self):
        return sum((linea.subtotal for linea in self.lineas.all()), start=0)

    @transaction.atomic
    def confirmar(self, usuario):
        """Impacta el stock y el PMP de cada producto de la compra."""
        if self.estado != self.BORRADOR:
            raise ValidationError('Solo se pueden confirmar compras en estado Borrador.')

        lineas = self.lineas.select_related('producto')
        if not lineas.exists():
            raise ValidationError('La compra no tiene líneas cargadas.')

        for linea in lineas:
            update_pmp(linea.producto, linea.cantidad, linea.precio_unitario)
            registrar_movimiento(
                producto=linea.producto,
                cantidad=linea.cantidad,
                tipo=MovimientoStock.ENTRADA,
                origen=MovimientoStock.ORIGEN_COMPRA,
                usuario=usuario,
                referencia_id=self.pk,
                motivo=f'Compra #{self.pk} a {self.proveedor}',
            )

        self.estado = self.CONFIRMADA
        self.save(update_fields=['estado'])

        # Interconexión con FINANZAS: genera el asiento contable automático.
        from finanzas.services import post_compra
        post_compra(self)


class CompraLinea(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='lineas_compra')
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f'{self.producto.codigo} x {self.cantidad}'
