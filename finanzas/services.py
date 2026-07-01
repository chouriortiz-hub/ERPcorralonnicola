"""
Generación automática de asientos contables (patrón de la guía, sección 8),
disparada desde `facturacion.models.Factura.marcar_autorizada` y
`compras.models.Compra.confirmar`.
"""
from django.db import transaction

from .models import CuentaContable, Journal


@transaction.atomic
def post_invoice(factura):
    """Venta facturada: Cliente/Caja (debe) contra Ventas + IVA (haber)."""
    Journal.objects.create(
        cuenta_codigo=CuentaContable.CLIENTES,
        debe=factura.total,
        haber=0,
        referencia_tipo='FACTURA',
        referencia_id=factura.pk,
        descripcion=f'Factura {factura.tipo_comprobante} {factura.numero} - {factura.cliente}',
    )
    Journal.objects.create(
        cuenta_codigo=CuentaContable.VENTAS,
        debe=0,
        haber=factura.subtotal,
        referencia_tipo='FACTURA',
        referencia_id=factura.pk,
        descripcion=f'Factura {factura.tipo_comprobante} {factura.numero} - {factura.cliente}',
    )
    Journal.objects.create(
        cuenta_codigo=CuentaContable.IVA_DEBITO_FISCAL,
        debe=0,
        haber=factura.iva,
        referencia_tipo='FACTURA',
        referencia_id=factura.pk,
        descripcion=f'IVA Factura {factura.tipo_comprobante} {factura.numero}',
    )


@transaction.atomic
def post_compra(compra):
    """Compra confirmada: Inventario (debe) contra Proveedores (haber)."""
    total = compra.total
    Journal.objects.create(
        cuenta_codigo=CuentaContable.INVENTARIO,
        debe=total,
        haber=0,
        referencia_tipo='COMPRA',
        referencia_id=compra.pk,
        descripcion=f'Compra #{compra.pk} - {compra.proveedor}',
    )
    Journal.objects.create(
        cuenta_codigo=CuentaContable.PROVEEDORES,
        debe=0,
        haber=total,
        referencia_tipo='COMPRA',
        referencia_id=compra.pk,
        descripcion=f'Compra #{compra.pk} - {compra.proveedor}',
    )
