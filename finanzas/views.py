from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Role
from core.permissions import es_administrador
from core.views_utils import exigir_permiso, paginar

from .models import CierreCaja, CuentaContable, Journal


def _parse_decimal(valor):
    try:
        return Decimal(str(valor).strip().replace(',', '.') or '0')
    except InvalidOperation:
        raise ValidationError('El monto ingresado no es un número válido.')


@login_required
def libro_diario(request):
    if (resp := exigir_permiso(request, 'finanzas', Role.SOLO_VISUALIZACION)):
        return resp

    cuenta = request.GET.get('cuenta', '')
    referencia_tipo = request.GET.get('referencia_tipo', '')

    asientos = Journal.objects.all()
    if cuenta:
        asientos = asientos.filter(cuenta_codigo=cuenta)
    if referencia_tipo:
        asientos = asientos.filter(referencia_tipo=referencia_tipo)

    totales = asientos.aggregate(total_debe=Sum('debe'), total_haber=Sum('haber'))

    return render(request, 'finanzas/libro_diario.html', {
        'asientos': paginar(request, asientos),
        'cuenta': cuenta, 'cuentas': CuentaContable.choices,
        'referencia_tipo': referencia_tipo,
        'total_debe': totales['total_debe'] or 0,
        'total_haber': totales['total_haber'] or 0,
    })


@login_required
def caja_actual(request):
    """Caja del vendedor logueado: abrir con un fondo inicial y, al terminar
    el turno, cerrar contando el efectivo real contra lo que el sistema
    esperaba según sus propios pedidos cargados en ese lapso."""
    if (resp := exigir_permiso(request, 'finanzas', Role.CREAR_MODIFICAR)):
        return resp

    caja_abierta = CierreCaja.objects.filter(usuario=request.user, estado=CierreCaja.ABIERTA).first()

    if request.method == 'POST':
        accion = request.POST.get('accion')
        try:
            if accion == 'abrir':
                if caja_abierta:
                    raise ValidationError('Ya tenés una caja abierta.')
                monto_apertura = _parse_decimal(request.POST.get('monto_apertura'))
                caja_abierta = CierreCaja.objects.create(usuario=request.user, monto_apertura=monto_apertura)
                messages.success(request, 'Caja abierta correctamente.')
            elif accion == 'cerrar':
                if not caja_abierta:
                    raise ValidationError('No tenés ninguna caja abierta para cerrar.')
                efectivo_contado = _parse_decimal(request.POST.get('efectivo_contado'))
                caja_abierta.cerrar(efectivo_contado=efectivo_contado, observaciones=request.POST.get('observaciones', ''))
                messages.success(request, f'Caja cerrada. Diferencia: ${caja_abierta.diferencia:.2f}')
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
        return redirect('finanzas:caja_actual')

    return render(request, 'finanzas/caja_actual.html', {'caja': caja_abierta})


@login_required
def caja_list(request):
    if (resp := exigir_permiso(request, 'finanzas', Role.SOLO_VISUALIZACION)):
        return resp

    cierres = CierreCaja.objects.select_related('usuario')
    if not es_administrador(request.user):
        cierres = cierres.filter(usuario=request.user)

    return render(request, 'finanzas/caja_list.html', {'cierres': paginar(request, cierres)})


@login_required
def caja_detalle(request, pk):
    if (resp := exigir_permiso(request, 'finanzas', Role.SOLO_VISUALIZACION)):
        return resp

    cierre = get_object_or_404(CierreCaja.objects.select_related('usuario'), pk=pk)
    if cierre.usuario_id != request.user.id and not es_administrador(request.user):
        messages.error(request, 'No podés ver la caja de otro usuario.')
        return redirect('finanzas:caja_list')

    return render(request, 'finanzas/caja_detalle.html', {'cierre': cierre})
