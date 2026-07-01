"""
Flujo completo de facturación: Pedido confirmado -> Factura -> CAE (ARCA).
Esta es la función que llaman las vistas del mostrador cuando el
vendedor aprieta "Facturar".
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from ventas.models import Pedido

from .models import Factura
from .services import ARCAIntegrationError, ARCAService


@transaction.atomic
def facturar_pedido(pedido: Pedido, punto_venta, tipo_comprobante, usuario):
    if pedido.estado != Pedido.CONFIRMADO:
        raise ValidationError('El pedido debe estar Confirmado (con stock ya impactado) antes de facturarse.')
    if hasattr(pedido, 'factura'):
        raise ValidationError('Este pedido ya tiene una factura asociada.')

    factura = Factura.objects.create(
        pedido=pedido,
        cliente=pedido.cliente,
        punto_venta=punto_venta,
        tipo_comprobante=tipo_comprobante,
        usuario=usuario,
    )
    factura.generar_desde_pedido()

    try:
        resultado = ARCAService().solicitar_cae(factura)
        factura.marcar_autorizada(
            cae=resultado['cae'],
            cae_vencimiento=resultado['cae_vencimiento'],
            numero=resultado['numero'],
        )
    except ARCAIntegrationError as e:
        factura.marcar_rechazada(motivo=str(e))
        raise

    return factura
