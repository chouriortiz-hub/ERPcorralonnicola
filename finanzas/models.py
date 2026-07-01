"""
Módulo FINANZAS (bonus, sugerido a partir de la sección 8 de la guía)
----------------------------------------------------------------------
Libro Diario con asientos automáticos: cada vez que se AUTORIZA una
factura o se CONFIRMA una compra, el sistema genera el asiento contable
correspondiente sin intervención manual. Cierra el círculo del ERP:
Stock <-> Ventas/Compras <-> Facturación <-> Finanzas.
"""
from django.db import models


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
