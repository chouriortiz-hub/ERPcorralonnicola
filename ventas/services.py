"""
Servicios de VENTAS: orquestación entre el carrito armado en la pantalla
"Nuevo Pedido" (búsqueda de productos + selección de cliente) y los
modelos de negocio (Presupuesto/Pedido). Separado de views.py para poder
reutilizarse desde cualquier otro punto de entrada (admin, futura API)
sin duplicar lógica.
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from stock.models import Producto

from .models import Cliente, Pedido, PedidoLinea, Presupuesto, PresupuestoLinea


def parsear_lineas_carrito(items):
    """
    Valida y normaliza la lista de items del carrito (ya deserializada de
    JSON) a una lista de dicts con el Producto ya resuelto:
        [{"producto_id": 1, "cantidad": "5.000", "precio_unitario": "1500.00", "sale_con_reparto": true}, ...]
    ->  [{"producto": <Producto>, "cantidad": Decimal, "precio_unitario": Decimal, "sale_con_reparto": bool}, ...]
    """
    if not isinstance(items, list) or not items:
        raise ValidationError('El carrito está vacío.')

    try:
        producto_ids = [int(item['producto_id']) for item in items]
    except (KeyError, TypeError, ValueError):
        raise ValidationError('El carrito tiene un producto inválido.')

    productos = Producto.objects.in_bulk(producto_ids)

    lineas = []
    for item in items:
        producto_id = int(item['producto_id'])
        producto = productos.get(producto_id)
        if producto is None or not producto.activo:
            raise ValidationError(f'El producto seleccionado (id {producto_id}) no existe o no está activo.')

        try:
            cantidad = Decimal(str(item.get('cantidad', '0')))
            precio_unitario = Decimal(str(item.get('precio_unitario', '0')))
        except InvalidOperation:
            raise ValidationError(f'Cantidad o precio inválido para "{producto.nombre}".')

        if cantidad <= 0:
            raise ValidationError(f'La cantidad de "{producto.nombre}" debe ser mayor a cero.')
        if precio_unitario < 0:
            raise ValidationError(f'El precio unitario de "{producto.nombre}" no puede ser negativo.')

        lineas.append({
            'producto': producto,
            'cantidad': cantidad,
            'precio_unitario': precio_unitario,
            'sale_con_reparto': bool(item.get('sale_con_reparto', False)),
        })

    return lineas


def resolver_cliente(data):
    """
    Devuelve el Cliente existente indicado por `cliente_id`, o crea uno
    nuevo con los datos `cliente_*` del formulario.
    """
    cliente_id = data.get('cliente_id')
    if cliente_id:
        try:
            return Cliente.objects.get(pk=int(cliente_id))
        except (Cliente.DoesNotExist, TypeError, ValueError):
            raise ValidationError('El cliente seleccionado no existe.')

    nombre = (data.get('cliente_nombre') or '').strip()
    if not nombre:
        raise ValidationError('Ingresá el nombre del cliente.')

    return Cliente.objects.create(
        nombre=nombre,
        cuit_dni=(data.get('cliente_cuit_dni') or '').strip() or None,
        condicion_iva=data.get('cliente_condicion_iva') or 'CONSUMIDOR_FINAL',
        direccion=(data.get('cliente_direccion') or '').strip(),
        telefono=(data.get('cliente_telefono') or '').strip(),
        email=(data.get('cliente_email') or '').strip() or None,
    )


@transaction.atomic
def crear_presupuesto_desde_carrito(cliente, vendedor, lineas, validez_dias=7, observaciones=''):
    """Presupuesto: cotización pura, nunca toca stock."""
    presupuesto = Presupuesto.objects.create(
        cliente=cliente,
        vendedor=vendedor,
        validez_dias=validez_dias,
        observaciones=observaciones,
    )
    for linea in lineas:
        PresupuestoLinea.objects.create(
            presupuesto=presupuesto,
            producto=linea['producto'],
            cantidad=linea['cantidad'],
            precio_unitario=linea['precio_unitario'],
        )
    return presupuesto


@transaction.atomic
def crear_pedido_desde_carrito(cliente, vendedor, lineas, direccion_entrega='', fecha_entrega_estimada=None, observaciones=''):
    """
    Crea el Pedido con sus líneas (cada una con su flag `sale_con_reparto`),
    infiere `tipo_entrega` y lo confirma: esto descuenta stock únicamente
    de las líneas que se retiran en el momento (ver Pedido.confirmar).
    """
    pedido = Pedido.objects.create(
        cliente=cliente,
        vendedor=vendedor,
        direccion_entrega=direccion_entrega,
        fecha_entrega_estimada=fecha_entrega_estimada,
        observaciones=observaciones,
    )
    for linea in lineas:
        PedidoLinea.objects.create(
            pedido=pedido,
            producto=linea['producto'],
            cantidad=linea['cantidad'],
            precio_unitario=linea['precio_unitario'],
            sale_con_reparto=linea['sale_con_reparto'],
        )
    pedido.actualizar_tipo_entrega()
    pedido.confirmar(usuario=vendedor)
    return pedido
