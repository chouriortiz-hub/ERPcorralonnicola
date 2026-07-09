from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from core.models import Role
from core.views_utils import exigir_permiso, paginar

from .models import CuentaContable, Journal


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
