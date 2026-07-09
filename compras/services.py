"""Servicios de COMPRAS: arma una Compra en borrador a partir del carrito de
la pantalla de alta, siguiendo el mismo patrón que ventas/services.py."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from stock.models import Producto

from .models import Compra, CompraLinea


def parsear_lineas_carrito(items):
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

        lineas.append({'producto': producto, 'cantidad': cantidad, 'precio_unitario': precio_unitario})

    return lineas


@transaction.atomic
def crear_compra_desde_carrito(proveedor, usuario, lineas, numero_comprobante='', observaciones=''):
    compra = Compra.objects.create(
        proveedor=proveedor,
        usuario=usuario,
        numero_comprobante=numero_comprobante,
        observaciones=observaciones,
    )
    for linea in lineas:
        CompraLinea.objects.create(
            compra=compra,
            producto=linea['producto'],
            cantidad=linea['cantidad'],
            precio_unitario=linea['precio_unitario'],
        )
    return compra
