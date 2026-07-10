import calendar
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Role
from core.permissions import tiene_permiso
from core.views_utils import exigir_permiso, paginar
from ventas.models import Pedido

from .forms import RepartoForm, VehiculoForm
from .models import Reparto, RepartoPedido, Vehiculo

MESES_ES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]
DIAS_SEMANA_ES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']


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


def _leer_cantidades_salida(request, reparto_pedido):
    """Lee del POST los campos `cantidad_<linea_id>` con lo que el
    repartidor cargó como salido para cada línea pendiente del pedido."""
    cantidades = {}
    for linea in reparto_pedido.pedido.lineas_pendientes_reparto:
        valor = request.POST.get(f'cantidad_{linea.pk}')
        if valor is None or not str(valor).strip():
            continue
        try:
            cantidad = Decimal(str(valor).strip().replace(',', '.'))
        except InvalidOperation:
            raise ValidationError(f'La cantidad cargada para "{linea.producto.nombre}" no es válida.')
        if cantidad > 0:
            cantidades[linea.pk] = cantidad
    return cantidades


def _pedidos_disponibles_qs():
    """Pedidos confirmados/facturados con líneas de reparto pendientes que
    no tienen ya un RepartoPedido pendiente de salida en otro reparto (si
    tuvieron una salida parcial o no salieron, el saldo vuelve a estar
    disponible para asignarse a un nuevo reparto)."""
    return Pedido.objects.filter(
        estado__in=[Pedido.CONFIRMADO, Pedido.FACTURADO],
        tipo_entrega=Pedido.ENTREGA_REPARTO,
        lineas__sale_con_reparto=True,
        lineas__producto__descuenta_stock=True,
        lineas__cantidad_salida__lt=F('lineas__cantidad'),
    ).exclude(
        repartos_asignados__estado_salida=RepartoPedido.PENDIENTE,
    ).select_related('cliente').distinct().order_by('-fecha')


@login_required
def reparto_form(request):
    if (resp := exigir_permiso(request, 'repartos', Role.CREAR_MODIFICAR)):
        return resp
    if request.method == 'POST':
        form = RepartoForm(request.POST)
        if form.is_valid():
            reparto = form.save()
            for pedido_id in request.POST.getlist('pedidos_seleccionados'):
                try:
                    reparto.agregar_pedido(Pedido.objects.get(pk=pedido_id))
                except (Pedido.DoesNotExist, ValueError, TypeError):
                    messages.error(request, f'El pedido #{pedido_id} no existe.')
                except ValidationError as e:
                    messages.error(
                        request,
                        f'Pedido #{pedido_id}: ' + (' '.join(e.messages) if hasattr(e, 'messages') else str(e)),
                    )
            messages.success(request, f'Reparto #{reparto.pk} creado.')
            return redirect('repartos:reparto_detalle', pk=reparto.pk)
    else:
        form = RepartoForm()
    return render(request, 'repartos/reparto_form.html', {
        'form': form, 'pedidos_disponibles': _pedidos_disponibles_qs(),
    })


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

    hay_pendientes = reparto.pedidos.filter(estado_salida=RepartoPedido.PENDIENTE).exists()
    return render(request, 'repartos/reparto_detalle.html', {'reparto': reparto, 'hay_pendientes': hay_pendientes})


@login_required
def repartopedido_salida(request, pk):
    if (resp := exigir_permiso(request, 'repartos', Role.CREAR_MODIFICAR)):
        return resp
    reparto_pedido = get_object_or_404(RepartoPedido, pk=pk)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        try:
            if accion == 'registrar_salida':
                cantidades = _leer_cantidades_salida(request, reparto_pedido)
                reparto_pedido.registrar_salida(usuario=request.user, cantidades=cantidades)
                if reparto_pedido.estado_salida == RepartoPedido.PARCIAL:
                    messages.success(
                        request,
                        f'Salida parcial registrada para el pedido #{reparto_pedido.pedido_id}: '
                        'el saldo pendiente queda disponible para un próximo reparto.',
                    )
                else:
                    messages.success(
                        request,
                        f'Pedido #{reparto_pedido.pedido_id} salió del depósito: se descontó su stock pendiente.',
                    )
            elif accion == 'no_salio':
                reparto_pedido.marcar_no_salio(motivo=request.POST.get('motivo', ''))
                messages.success(request, f'Pedido #{reparto_pedido.pedido_id} marcado como no salido.')
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
    return redirect('repartos:reparto_detalle', pk=reparto_pedido.reparto_id)


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
    ).exclude(
        repartos_asignados__estado_salida=RepartoPedido.PENDIENTE,
    ).select_related('cliente').distinct()
    if q:
        pedidos = pedidos.filter(Q(pk=q) if q.isdigit() else Q(cliente__nombre__icontains=q))

    resultados = [{
        'id': p.id, 'cliente': p.cliente.nombre, 'direccion': p.direccion_entrega, 'estado': p.get_estado_display(),
    } for p in pedidos.order_by('-fecha')[:20] if p.tiene_lineas_pendientes_reparto]

    return JsonResponse({'resultados': resultados})


@login_required
def calendario(request):
    if (resp := exigir_permiso(request, 'repartos', Role.SOLO_VISUALIZACION)):
        return resp

    hoy = date.today()
    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))
        if not (1 <= mes <= 12):
            raise ValueError
    except (TypeError, ValueError):
        anio, mes = hoy.year, hoy.month

    conteos = (
        RepartoPedido.objects
        .filter(reparto__fecha__year=anio, reparto__fecha__month=mes)
        .values('reparto__fecha')
        .annotate(
            total=Count('id'),
            pendientes=Count('id', filter=Q(estado_salida=RepartoPedido.PENDIENTE)),
        )
    )
    conteo_por_dia = {c['reparto__fecha'].day: c for c in conteos}

    semanas = []
    for semana in calendar.Calendar(firstweekday=0).monthdayscalendar(anio, mes):
        fila = []
        for numero in semana:
            if numero == 0:
                fila.append(None)
                continue
            fecha_dia = date(anio, mes, numero)
            info = conteo_por_dia.get(numero)
            fila.append({
                'numero': numero,
                'iso': fecha_dia.isoformat(),
                'total': info['total'] if info else 0,
                'pendientes': info['pendientes'] if info else 0,
                'es_hoy': fecha_dia == hoy,
            })
        semanas.append(fila)

    mes_anterior = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    mes_siguiente = (anio, mes + 1) if mes < 12 else (anio + 1, 1)

    return render(request, 'repartos/calendario.html', {
        'anio': anio, 'mes': mes, 'nombre_mes': MESES_ES[mes],
        'dias_semana': DIAS_SEMANA_ES, 'semanas': semanas,
        'mes_anterior': mes_anterior, 'mes_siguiente': mes_siguiente,
    })


@login_required
def reparto_dia(request, fecha):
    if (resp := exigir_permiso(request, 'repartos', Role.SOLO_VISUALIZACION)):
        return resp

    try:
        fecha_dia = date.fromisoformat(fecha)
    except ValueError:
        raise Http404('Fecha inválida.')

    if request.method == 'POST':
        if not tiene_permiso(request.user, 'repartos', Role.CREAR_MODIFICAR):
            messages.error(request, 'No tenés permiso para modificar repartos.')
        else:
            reparto_pedido = get_object_or_404(
                RepartoPedido, pk=request.POST.get('reparto_pedido_id'), reparto__fecha=fecha_dia,
            )
            accion = request.POST.get('accion')
            try:
                if accion == 'registrar_salida':
                    cantidades = _leer_cantidades_salida(request, reparto_pedido)
                    reparto_pedido.registrar_salida(usuario=request.user, cantidades=cantidades)
                    if reparto_pedido.estado_salida == RepartoPedido.PARCIAL:
                        messages.success(
                            request,
                            f'Salida parcial registrada para el pedido #{reparto_pedido.pedido_id}: '
                            'el saldo pendiente queda disponible para un próximo reparto.',
                        )
                    else:
                        messages.success(
                            request,
                            f'Pedido #{reparto_pedido.pedido_id} salió del depósito: se descontó su stock pendiente.',
                        )
                elif accion == 'no_salio':
                    reparto_pedido.marcar_no_salio(motivo=request.POST.get('motivo', ''))
                    messages.success(request, f'Pedido #{reparto_pedido.pedido_id} marcado como no salido.')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
        return redirect('repartos:reparto_dia', fecha=fecha)

    repartos_pedidos = (
        RepartoPedido.objects
        .filter(reparto__fecha=fecha_dia)
        .select_related('reparto', 'reparto__chofer', 'reparto__vehiculo', 'pedido', 'pedido__cliente')
        .order_by('reparto__chofer__username', 'orden')
    )

    return render(request, 'repartos/reparto_dia.html', {
        'fecha': fecha_dia, 'repartos_pedidos': repartos_pedidos,
    })


@login_required
def pedidos_disponibles(request):
    if (resp := exigir_permiso(request, 'repartos', Role.SOLO_VISUALIZACION)):
        return resp

    if request.method == 'POST':
        if not tiene_permiso(request.user, 'repartos', Role.CREAR_MODIFICAR):
            messages.error(request, 'No tenés permiso para modificar repartos.')
        else:
            try:
                reparto = Reparto.objects.get(pk=request.POST.get('reparto_id'), estado=Reparto.PROGRAMADO)
                pedido = Pedido.objects.get(pk=request.POST.get('pedido_id'))
                reparto.agregar_pedido(pedido)
                messages.success(request, f'Pedido #{pedido.pk} agregado al reparto #{reparto.pk}.')
            except (Reparto.DoesNotExist, Pedido.DoesNotExist, ValueError, TypeError):
                messages.error(request, 'El reparto o el pedido seleccionado no existen.')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
        return redirect('repartos:pedidos_disponibles')

    pedidos = _pedidos_disponibles_qs()

    repartos_programados = (
        Reparto.objects.filter(estado=Reparto.PROGRAMADO)
        .select_related('chofer', 'vehiculo').order_by('fecha')
    )

    return render(request, 'repartos/pedidos_disponibles.html', {
        'pedidos': paginar(request, pedidos), 'repartos_programados': repartos_programados,
    })
