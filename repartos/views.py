from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Role
from core.permissions import tiene_permiso
from core.views_utils import exigir_permiso, paginar
from ventas.models import Pedido

from .forms import RepartoForm, VehiculoForm
from .models import Reparto, RepartoPedido, Vehiculo


@login_required
def vehiculo_list(request):
    if (resp := exigir_permiso(request, 'repartos', Role.SOLO_VISUALIZACION)):
        return resp
    vehiculos = Vehiculo.objects.all().order_by('patente')
    return render(request, 'repartos/vehiculo_list.html', {'vehiculos': paginar(request, vehiculos)})


@login_required
def vehiculo_form(request, pk=None):
    if (resp := exigir_permiso(request, 'repartos', Role.CREAR_MODIFICAR)):
        return resp
    vehiculo = get_object_or_404(Vehiculo, pk=pk) if pk else None
    if request.method == 'POST':
        form = VehiculoForm(request.POST, instance=vehiculo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehículo guardado correctamente.')
            return redirect('repartos:vehiculo_list')
    else:
        form = VehiculoForm(instance=vehiculo)
    return render(request, 'repartos/vehiculo_form.html', {'form': form, 'vehiculo': vehiculo})


@login_required
def reparto_list(request):
    if (resp := exigir_permiso(request, 'repartos', Role.SOLO_VISUALIZACION)):
        return resp
    estado = request.GET.get('estado', '')
    repartos = Reparto.objects.select_related('chofer', 'vehiculo')
    if estado:
        repartos = repartos.filter(estado=estado)
    return render(request, 'repartos/reparto_list.html', {
        'repartos': paginar(request, repartos), 'estado': estado, 'estados': Reparto.ESTADO_CHOICES,
    })


@login_required
def reparto_form(request):
    if (resp := exigir_permiso(request, 'repartos', Role.CREAR_MODIFICAR)):
        return resp
    if request.method == 'POST':
        form = RepartoForm(request.POST)
        if form.is_valid():
            reparto = form.save()
            messages.success(request, f'Reparto #{reparto.pk} creado.')
            return redirect('repartos:reparto_detalle', pk=reparto.pk)
    else:
        form = RepartoForm()
    return render(request, 'repartos/reparto_form.html', {'form': form})


@login_required
def reparto_detalle(request, pk):
    if (resp := exigir_permiso(request, 'repartos', Role.SOLO_VISUALIZACION)):
        return resp
    reparto = get_object_or_404(Reparto.objects.select_related('chofer', 'vehiculo'), pk=pk)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if not tiene_permiso(request.user, 'repartos', Role.CREAR_MODIFICAR):
            messages.error(request, 'No tenés permiso para modificar repartos.')
        elif accion == 'salida':
            try:
                reparto.marcar_salida(usuario=request.user)
                messages.success(request, f'Reparto #{reparto.pk} en curso: se descontó el stock pendiente.')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
        elif accion == 'agregar_pedido':
            try:
                pedido = Pedido.objects.get(pk=request.POST.get('pedido_id'))
                reparto.agregar_pedido(pedido)
                messages.success(request, f'Pedido #{pedido.pk} agregado al reparto.')
            except (Pedido.DoesNotExist, ValueError, TypeError):
                messages.error(request, 'El pedido seleccionado no existe.')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
        return redirect('repartos:reparto_detalle', pk=reparto.pk)

    return render(request, 'repartos/reparto_detalle.html', {'reparto': reparto})


@login_required
def repartopedido_entrega(request, pk):
    if (resp := exigir_permiso(request, 'repartos', Role.CREAR_MODIFICAR)):
        return resp
    reparto_pedido = get_object_or_404(RepartoPedido, pk=pk)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        try:
            if accion == 'entregado':
                reparto_pedido.marcar_entregado()
                messages.success(request, 'Entrega registrada.')
            elif accion == 'no_entregado':
                reparto_pedido.marcar_no_entregado(motivo=request.POST.get('motivo', ''))
                messages.success(request, 'Se registró la no entrega.')
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
    return redirect('repartos:reparto_detalle', pk=reparto_pedido.reparto_id)


@login_required
def buscar_pedidos_pendientes(request):
    if not tiene_permiso(request.user, 'repartos', Role.SOLO_VISUALIZACION):
        return JsonResponse({'error': 'Sin permiso.'}, status=403)

    q = request.GET.get('q', '').strip()
    pedidos = Pedido.objects.filter(
        estado__in=[Pedido.CONFIRMADO, Pedido.FACTURADO],
        tipo_entrega=Pedido.ENTREGA_REPARTO,
        reparto_asignado__isnull=True,
    ).select_related('cliente').distinct()
    if q:
        pedidos = pedidos.filter(Q(pk=q) if q.isdigit() else Q(cliente__nombre__icontains=q))

    resultados = [{
        'id': p.id, 'cliente': p.cliente.nombre, 'direccion': p.direccion_entrega, 'estado': p.get_estado_display(),
    } for p in pedidos.order_by('-fecha')[:20] if p.tiene_lineas_pendientes_reparto]

    return JsonResponse({'resultados': resultados})
