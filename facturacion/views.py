from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Role
from core.views_utils import exigir_permiso, paginar

from .forms import PuntoVentaForm
from .models import Factura, PuntoVenta


@login_required
def factura_imprimir(request, pk):
    factura = get_object_or_404(Factura, pk=pk)
    return render(request, 'facturacion/factura_print.html', {'factura': factura})


@login_required
def factura_list(request):
    if (resp := exigir_permiso(request, 'facturacion', Role.SOLO_VISUALIZACION)):
        return resp
    estado = request.GET.get('estado', '')
    facturas = Factura.objects.select_related('cliente', 'punto_venta')
    if estado:
        facturas = facturas.filter(estado=estado)
    return render(request, 'facturacion/factura_list.html', {
        'facturas': paginar(request, facturas), 'estado': estado, 'estados': Factura.ESTADO_CHOICES,
    })


@login_required
def factura_detalle(request, pk):
    if (resp := exigir_permiso(request, 'facturacion', Role.SOLO_VISUALIZACION)):
        return resp
    factura = get_object_or_404(Factura.objects.select_related('cliente', 'punto_venta', 'pedido'), pk=pk)
    return render(request, 'facturacion/factura_detalle.html', {'factura': factura})


@login_required
def puntoventa_list(request):
    if (resp := exigir_permiso(request, 'facturacion', Role.SOLO_VISUALIZACION)):
        return resp
    return render(request, 'facturacion/puntoventa_list.html', {'puntos_venta': PuntoVenta.objects.all().order_by('numero')})


@login_required
def puntoventa_form(request, pk=None):
    if (resp := exigir_permiso(request, 'facturacion', Role.ADMINISTRADOR)):
        return resp
    punto_venta = get_object_or_404(PuntoVenta, pk=pk) if pk else None
    if request.method == 'POST':
        form = PuntoVentaForm(request.POST, instance=punto_venta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Punto de venta guardado correctamente.')
            return redirect('facturacion:puntoventa_list')
    else:
        form = PuntoVentaForm(instance=punto_venta)
    return render(request, 'facturacion/puntoventa_form.html', {'form': form, 'punto_venta': punto_venta})
