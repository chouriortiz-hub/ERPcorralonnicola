"""
Vistas de VENTAS: la pantalla "Nuevo Pedido" es el único punto de entrada
operativo (fuera del admin) para armar un carrito de productos y resolverlo
como Presupuesto (cotización, no toca stock) o como Pedido facturado
(descuenta stock de mostrador al toque, deja pendientes las líneas que
salen con reparto). Gatea el acceso con el sistema de permisos consolidado
de `core.permissions` (hasta ahora sin uso porque no existían vistas propias).
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Role
from core.permissions import tiene_permiso
from core.views_utils import exigir_permiso, paginar
from facturacion.actions import facturar_pedido_completo
from facturacion.models import PuntoVenta, TipoComprobante
from stock.models import Producto

from .forms import ClienteForm
from .models import Cliente, Pedido, Presupuesto
from .services import (
    crear_pedido_desde_carrito,
    crear_presupuesto_desde_carrito,
    parsear_lineas_carrito,
    resolver_cliente,
)


@login_required
def nuevo_pedido(request):
    if not tiene_permiso(request.user, 'ventas', Role.CREAR_MODIFICAR):
        messages.error(request, 'No tenés permiso para cargar pedidos.')
        return redirect('admin:index')

    puede_facturar = tiene_permiso(request.user, 'facturacion', Role.CREAR_MODIFICAR)
    contexto_base = {
        'puede_facturar': puede_facturar,
        'puntos_venta': PuntoVenta.objects.all(),
        'tipos_comprobante': TipoComprobante.choices,
        'condiciones_iva': Cliente._meta.get_field('condicion_iva').choices,
    }

    if request.method == 'POST':
        modo = request.POST.get('modo')
        carrito_json = request.POST.get('carrito_json', '[]')

        try:
            try:
                items = json.loads(carrito_json)
            except json.JSONDecodeError:
                raise ValidationError('El carrito enviado es inválido.')

            lineas = parsear_lineas_carrito(items)
            cliente = resolver_cliente(request.POST)

            if modo == 'presupuesto':
                presupuesto = crear_presupuesto_desde_carrito(
                    cliente=cliente,
                    vendedor=request.user,
                    lineas=lineas,
                    validez_dias=int(request.POST.get('validez_dias') or 7),
                    observaciones=request.POST.get('observaciones', ''),
                )
                return redirect('ventas:presupuesto_imprimir', pk=presupuesto.pk)

            elif modo == 'facturar':
                if not puede_facturar:
                    raise ValidationError('No tenés permiso para facturar pedidos.')

                try:
                    punto_venta = PuntoVenta.objects.get(pk=request.POST.get('punto_venta_id'))
                except (PuntoVenta.DoesNotExist, ValueError, TypeError):
                    raise ValidationError('Elegí un punto de venta válido.')

                tipo_comprobante = request.POST.get('tipo_comprobante')
                if tipo_comprobante not in TipoComprobante.values:
                    raise ValidationError('Elegí un tipo de comprobante válido.')

                pedido = crear_pedido_desde_carrito(
                    cliente=cliente,
                    vendedor=request.user,
                    lineas=lineas,
                    direccion_entrega=request.POST.get('direccion_entrega', ''),
                    fecha_entrega_estimada=request.POST.get('fecha_entrega_estimada') or None,
                    observaciones=request.POST.get('observaciones', ''),
                )
                factura = facturar_pedido_completo(
                    pedido=pedido,
                    punto_venta=punto_venta,
                    tipo_comprobante=tipo_comprobante,
                    usuario=request.user,
                )
                if pedido.tiene_lineas_pendientes_reparto:
                    messages.info(
                        request,
                        f'Pedido #{pedido.pk} facturado. Tiene líneas pendientes de reparto: '
                        'asignalo a un Reparto desde el panel para descontar ese stock cuando salga.'
                    )
                return redirect('facturacion:factura_imprimir', pk=factura.pk)

            else:
                raise ValidationError('Elegí una acción: Presupuesto o Facturar.')

        except ValidationError as e:
            mensaje = ' '.join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, mensaje)
            return render(request, 'ventas/nuevo_pedido.html', {
                **contexto_base,
                'carrito_json': carrito_json,
                'modo': modo,
            })

    return render(request, 'ventas/nuevo_pedido.html', {
        **contexto_base,
        'carrito_json': '[]',
        'modo': '',
    })


@login_required
def buscar_productos(request):
    if not tiene_permiso(request.user, 'ventas', Role.SOLO_VISUALIZACION):
        return JsonResponse({'error': 'Sin permiso.'}, status=403)

    q = request.GET.get('q', '').strip()
    productos = Producto.objects.filter(activo=True)
    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q))

    resultados = [{
        'id': p.id,
        'codigo': p.codigo,
        'nombre': p.nombre,
        'stock_actual': str(p.stock_actual),
        'unidad_medida': p.get_unidad_medida_display(),
        'precio_venta': str(p.precio_venta),
        'descuenta_stock': p.descuenta_stock,
    } for p in productos.order_by('nombre')[:20]]

    return JsonResponse({'resultados': resultados})


@login_required
def buscar_clientes(request):
    if not tiene_permiso(request.user, 'ventas', Role.SOLO_VISUALIZACION):
        return JsonResponse({'error': 'Sin permiso.'}, status=403)

    q = request.GET.get('q', '').strip()
    clientes = Cliente.objects.filter(activo=True)
    if q:
        clientes = clientes.filter(nombre__icontains=q)

    resultados = [{
        'id': c.id,
        'nombre': c.nombre,
        'cuit_dni': c.cuit_dni or '',
        'direccion': c.direccion,
        'condicion_iva': c.condicion_iva,
    } for c in clientes.order_by('nombre')[:20]]

    return JsonResponse({'resultados': resultados})


@login_required
def presupuesto_imprimir(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    return render(request, 'ventas/presupuesto_print.html', {'presupuesto': presupuesto})


@login_required
def cliente_list(request):
    if (resp := exigir_permiso(request, 'ventas', Role.SOLO_VISUALIZACION)):
        return resp
    q = request.GET.get('q', '').strip()
    clientes = Cliente.objects.all().order_by('nombre')
    if q:
        clientes = clientes.filter(Q(nombre__icontains=q) | Q(cuit_dni__icontains=q))
    return render(request, 'ventas/cliente_list.html', {'clientes': paginar(request, clientes), 'q': q})


@login_required
def cliente_form(request, pk=None):
    if (resp := exigir_permiso(request, 'ventas', Role.CREAR_MODIFICAR)):
        return resp
    cliente = get_object_or_404(Cliente, pk=pk) if pk else None
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente guardado correctamente.')
            return redirect('ventas:cliente_list')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'ventas/cliente_form.html', {'form': form, 'cliente': cliente})


@login_required
def cliente_toggle(request, pk):
    if (resp := exigir_permiso(request, 'ventas', Role.CREAR_MODIFICAR)):
        return resp
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.activo = not cliente.activo
        cliente.save(update_fields=['activo'])
        messages.success(request, f'Cliente {"activado" if cliente.activo else "desactivado"}.')
    return redirect('ventas:cliente_list')


@login_required
def presupuesto_list(request):
    if (resp := exigir_permiso(request, 'ventas', Role.SOLO_VISUALIZACION)):
        return resp
    estado = request.GET.get('estado', '')
    presupuestos = Presupuesto.objects.select_related('cliente', 'vendedor')
    if estado:
        presupuestos = presupuestos.filter(estado=estado)
    return render(request, 'ventas/presupuesto_list.html', {
        'presupuestos': paginar(request, presupuestos),
        'estado': estado, 'estados': Presupuesto.ESTADO_CHOICES,
    })


@login_required
def presupuesto_detalle(request, pk):
    if (resp := exigir_permiso(request, 'ventas', Role.SOLO_VISUALIZACION)):
        return resp
    presupuesto = get_object_or_404(Presupuesto.objects.select_related('cliente', 'vendedor'), pk=pk)

    if request.method == 'POST' and request.POST.get('accion') == 'convertir':
        if not tiene_permiso(request.user, 'ventas', Role.CREAR_MODIFICAR):
            messages.error(request, 'No tenés permiso para convertir presupuestos.')
        else:
            try:
                pedido = presupuesto.convertir_a_pedido(usuario=request.user)
                messages.success(request, f'Presupuesto convertido a Pedido #{pedido.pk}.')
                return redirect('ventas:pedido_detalle', pk=pedido.pk)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))

    return render(request, 'ventas/presupuesto_detalle.html', {'presupuesto': presupuesto})


@login_required
def pedido_list(request):
    if (resp := exigir_permiso(request, 'ventas', Role.SOLO_VISUALIZACION)):
        return resp
    estado = request.GET.get('estado', '')
    pedidos = Pedido.objects.select_related('cliente', 'vendedor')
    if estado:
        pedidos = pedidos.filter(estado=estado)
    return render(request, 'ventas/pedido_list.html', {
        'pedidos': paginar(request, pedidos),
        'estado': estado, 'estados': Pedido.ESTADO_CHOICES,
    })


@login_required
def pedido_detalle(request, pk):
    if (resp := exigir_permiso(request, 'ventas', Role.SOLO_VISUALIZACION)):
        return resp
    pedido = get_object_or_404(Pedido.objects.select_related('cliente', 'vendedor'), pk=pk)

    if request.method == 'POST' and request.POST.get('accion') == 'confirmar':
        if not tiene_permiso(request.user, 'ventas', Role.CREAR_MODIFICAR):
            messages.error(request, 'No tenés permiso para confirmar pedidos.')
        else:
            try:
                pedido.confirmar(usuario=request.user)
                messages.success(request, f'Pedido #{pedido.pk} confirmado.')
                return redirect('ventas:pedido_detalle', pk=pedido.pk)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))

    return render(request, 'ventas/pedido_detalle.html', {'pedido': pedido})
