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
    if hasattr(pedido, 'factura') and pedido.factura.estado != Factura.RECHAZADA:
        raise ValidationError('Este pedido ya tiene una factura autorizada o pendiente.')
    if hasattr(pedido, 'factura'):
        # La factura previa fue rechazada por ARCA: se descarta el intento
        # fallido y se genera una nueva, para permitir corregir y reintentar.
        pedido.factura.delete()

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


def facturar_pedido_completo(pedido: Pedido, punto_venta, tipo_comprobante, usuario):
    """
    Punto de entrada para el flujo "Facturar" de la pantalla de Nuevo
    Pedido: el pedido ya fue creado y confirmado (con el stock de mostrador
    ya descontado) en un paso previo e independiente. Acá solo se dispara
    la facturación.

    A propósito NO se envuelve esto en el mismo atomic que la creación del
    pedido: si ARCA rechaza el comprobante, la mercadería de mostrador ya
    salió físicamente del depósito (no tiene sentido revertirla), y tanto
    el Pedido (CONFIRMADO) como la Factura (RECHAZADA, con motivo) quedan
    persistidos para poder corregir los datos y reintentar.
    """
    return facturar_pedido(pedido, punto_venta, tipo_comprobante, usuario)
