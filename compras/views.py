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
from stock.models import Proveedor

from .models import Compra
from .services import crear_compra_desde_carrito, parsear_lineas_carrito


@login_required
def compra_list(request):
    if (resp := exigir_permiso(request, 'compras', Role.SOLO_VISUALIZACION)):
        return resp
    estado = request.GET.get('estado', '')
    compras = Compra.objects.select_related('proveedor', 'usuario')
    if estado:
        compras = compras.filter(estado=estado)
    return render(request, 'compras/compra_list.html', {
        'compras': paginar(request, compras), 'estado': estado, 'estados': Compra.ESTADO_CHOICES,
    })


@login_required
def compra_form(request):
    if (resp := exigir_permiso(request, 'compras', Role.CREAR_MODIFICAR)):
        return resp

    if request.method == 'POST':
        carrito_json = request.POST.get('carrito_json', '[]')
        try:
            try:
                items = json.loads(carrito_json)
            except json.JSONDecodeError:
                raise ValidationError('El carrito enviado es inválido.')

            lineas = parsear_lineas_carrito(items)
            try:
                proveedor = Proveedor.objects.get(pk=request.POST.get('proveedor_id'))
            except (Proveedor.DoesNotExist, ValueError, TypeError):
                raise ValidationError('Elegí un proveedor válido.')

            compra = crear_compra_desde_carrito(
                proveedor=proveedor,
                usuario=request.user,
                lineas=lineas,
                numero_comprobante=request.POST.get('numero_comprobante', ''),
                observaciones=request.POST.get('observaciones', ''),
            )
            messages.success(request, f'Compra #{compra.pk} cargada como borrador.')
            return redirect('compras:compra_detalle', pk=compra.pk)

        except ValidationError as e:
            mensaje = ' '.join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, mensaje)
            return render(request, 'compras/compra_form.html', {'carrito_json': carrito_json})

    return render(request, 'compras/compra_form.html', {'carrito_json': '[]'})


@login_required
def compra_detalle(request, pk):
    if (resp := exigir_permiso(request, 'compras', Role.SOLO_VISUALIZACION)):
        return resp

    compra = get_object_or_404(Compra.objects.select_related('proveedor', 'usuario'), pk=pk)

    if request.method == 'POST' and request.POST.get('accion') == 'confirmar':
        if not tiene_permiso(request.user, 'compras', Role.CREAR_MODIFICAR):
            messages.error(request, 'No tenés permiso para confirmar compras.')
        else:
            try:
                compra.confirmar(usuario=request.user)
                messages.success(request, f'Compra #{compra.pk} confirmada.')
                return redirect('compras:compra_detalle', pk=compra.pk)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))

    return render(request, 'compras/compra_detalle.html', {'compra': compra})


@login_required
def buscar_proveedores(request):
    if not tiene_permiso(request.user, 'compras', Role.SOLO_VISUALIZACION):
        return JsonResponse({'error': 'Sin permiso.'}, status=403)

    q = request.GET.get('q', '').strip()
    proveedores = Proveedor.objects.filter(activo=True)
    if q:
        proveedores = proveedores.filter(Q(nombre__icontains=q) | Q(cuit__icontains=q))

    resultados = [{
        'id': p.id, 'nombre': p.nombre, 'cuit': p.cuit or '',
    } for p in proveedores.order_by('nombre')[:20]]

    return JsonResponse({'resultados': resultados})
