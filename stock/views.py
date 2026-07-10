import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import Role
from core.permissions import tiene_permiso
from core.views_utils import exigir_permiso, paginar

from . import services
from .forms import AjusteStockForm, BoletaForm, CategoriaForm, ImportarExcelForm, NotaForm, ProductoForm, ProveedorForm
from .models import Boleta, Categoria, MovimientoStock, Nota, Producto, Proveedor, registrar_movimiento


@login_required
def categoria_list(request):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    q = request.GET.get('q', '').strip()
    categorias = Categoria.objects.all().order_by('nombre')
    if q:
        categorias = categorias.filter(nombre__icontains=q)
    return render(request, 'stock/categoria_list.html', {'categorias': paginar(request, categorias), 'q': q})


@login_required
def categoria_form(request, pk=None):
    if (resp := exigir_permiso(request, 'stock', Role.CREAR_MODIFICAR)):
        return resp
    categoria = get_object_or_404(Categoria, pk=pk) if pk else None
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría guardada correctamente.')
            return redirect('stock:categoria_list')
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'stock/categoria_form.html', {'form': form, 'categoria': categoria})


@login_required
def proveedor_list(request):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    q = request.GET.get('q', '').strip()
    proveedores = Proveedor.objects.all().order_by('nombre')
    if q:
        proveedores = proveedores.filter(Q(nombre__icontains=q) | Q(cuit__icontains=q))
    return render(request, 'stock/proveedor_list.html', {'proveedores': paginar(request, proveedores), 'q': q})


@login_required
def proveedor_form(request, pk=None):
    if (resp := exigir_permiso(request, 'stock', Role.CREAR_MODIFICAR)):
        return resp
    proveedor = get_object_or_404(Proveedor, pk=pk) if pk else None
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor guardado correctamente.')
            return redirect('stock:proveedor_list')
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'stock/proveedor_form.html', {'form': form, 'proveedor': proveedor})


@login_required
def producto_list(request):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    q = request.GET.get('q', '').strip()
    productos = Producto.objects.select_related('categoria').order_by('nombre')
    if q:
        productos = productos.filter(Q(codigo__icontains=q) | Q(nombre__icontains=q))
    return render(request, 'stock/producto_list.html', {'productos': paginar(request, productos), 'q': q})


@login_required
def producto_form(request, pk=None):
    if (resp := exigir_permiso(request, 'stock', Role.CREAR_MODIFICAR)):
        return resp
    producto = get_object_or_404(Producto, pk=pk) if pk else None
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto guardado correctamente.')
            return redirect('stock:producto_list')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'stock/producto_form.html', {'form': form, 'producto': producto})


@login_required
def producto_toggle(request, pk):
    if (resp := exigir_permiso(request, 'stock', Role.CREAR_MODIFICAR)):
        return resp
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        producto.activo = not producto.activo
        producto.save(update_fields=['activo', 'actualizado'])
        messages.success(request, f'Producto {"activado" if producto.activo else "desactivado"}.')
    return redirect('stock:producto_list')


@login_required
def movimiento_list(request):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    periodo = request.GET.get('periodo', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')

    movimientos = MovimientoStock.objects.select_related('producto', 'usuario')
    if q:
        movimientos = movimientos.filter(Q(producto__codigo__icontains=q) | Q(producto__nombre__icontains=q))
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)

    hoy = timezone.localdate()
    if periodo == 'dia':
        movimientos = movimientos.filter(fecha__date=hoy)
    elif periodo == 'semana':
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        movimientos = movimientos.filter(fecha__date__gte=inicio_semana, fecha__date__lte=hoy)
    elif periodo == 'mes':
        movimientos = movimientos.filter(fecha__year=hoy.year, fecha__month=hoy.month)
    elif periodo == 'rango' and (desde or hasta):
        if desde:
            movimientos = movimientos.filter(fecha__date__gte=desde)
        if hasta:
            movimientos = movimientos.filter(fecha__date__lte=hasta)

    resumen = services.resumen_movimientos(movimientos)

    return render(request, 'stock/movimiento_list.html', {
        'movimientos': paginar(request, movimientos),
        'q': q, 'tipo': tipo, 'periodo': periodo, 'desde': desde, 'hasta': hasta,
        'tipos': MovimientoStock.TIPO_CHOICES,
        **resumen,
    })


@login_required
def dashboard_stock(request):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    return render(request, 'stock/dashboard.html', services.resumen_stock())


@login_required
def buscar_productos(request):
    if not tiene_permiso(request.user, 'stock', Role.SOLO_VISUALIZACION):
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
    } for p in productos.order_by('nombre')[:20]]

    return JsonResponse({'resultados': resultados})


@login_required
def buscar_movimientos(request):
    if not tiene_permiso(request.user, 'stock', Role.SOLO_VISUALIZACION):
        return JsonResponse({'error': 'Sin permiso.'}, status=403)

    q = request.GET.get('q', '').strip()
    movimientos = MovimientoStock.objects.select_related('producto').order_by('-fecha')
    if q:
        movimientos = movimientos.filter(
            Q(producto__codigo__icontains=q) | Q(producto__nombre__icontains=q) | Q(motivo__icontains=q)
        )

    resultados = [{
        'id': m.id,
        'fecha': m.fecha.strftime('%d/%m/%Y %H:%M'),
        'tipo': m.get_tipo_display(),
        'producto': f'{m.producto.codigo} - {m.producto.nombre}',
        'cantidad': str(m.cantidad),
        'origen': m.get_origen_display(),
    } for m in movimientos[:20]]

    return JsonResponse({'resultados': resultados})


@login_required
def boleta_list(request):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    boletas = Boleta.objects.select_related('usuario')
    if q:
        boletas = boletas.filter(numero__icontains=q)
    if tipo:
        boletas = boletas.filter(tipo=tipo)
    return render(request, 'stock/boleta_list.html', {
        'boletas': paginar(request, boletas), 'q': q, 'tipo': tipo,
        'tipos': Boleta.TIPO_CHOICES,
    })


@login_required
def boleta_form(request):
    if (resp := exigir_permiso(request, 'stock', Role.CREAR_MODIFICAR)):
        return resp

    productos_json = json.dumps([
        {'id': p.id, 'codigo': p.codigo, 'nombre': p.nombre, 'unidad_medida': p.get_unidad_medida_display()}
        for p in Producto.objects.filter(activo=True)
    ])

    if request.method == 'POST':
        form = BoletaForm(request.POST, request.FILES)
        items_json = request.POST.get('items_json', '[]')
        if form.is_valid():
            try:
                items = json.loads(items_json)
                lineas = services.parsear_items_boleta(items)
                boleta = services.crear_boleta(form.save(commit=False), lineas, request.user)
                messages.success(request, f'Boleta #{boleta.numero} confirmada: se aplicaron {len(lineas)} movimiento(s) de stock.')
                return redirect('stock:boleta_detalle', boleta.pk)
            except (ValidationError, json.JSONDecodeError) as e:
                mensaje = ' '.join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, mensaje)
        return render(request, 'stock/boleta_form.html', {
            'form': form, 'productos_json': productos_json, 'items_json': items_json,
        })

    form = BoletaForm()
    return render(request, 'stock/boleta_form.html', {
        'form': form, 'productos_json': productos_json, 'items_json': '[]',
    })


@login_required
def boleta_detalle(request, pk):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    boleta = get_object_or_404(Boleta.objects.select_related('usuario').prefetch_related('items__producto'), pk=pk)
    puede_ajustar = exigir_permiso(request, 'stock', Role.ADMINISTRADOR) is None
    return render(request, 'stock/boleta_detalle.html', {'boleta': boleta, 'puede_ajustar': puede_ajustar})


@login_required
def boleta_ajustar(request, pk):
    if (resp := exigir_permiso(request, 'stock', Role.ADMINISTRADOR)):
        return resp
    boleta = get_object_or_404(Boleta, pk=pk)
    if boleta.estado != Boleta.CONFIRMADA:
        messages.error(request, 'Solo se pueden ajustar boletas confirmadas.')
        return redirect('stock:boleta_detalle', boleta.pk)

    productos_json = json.dumps([
        {'id': p.id, 'codigo': p.codigo, 'nombre': p.nombre, 'unidad_medida': p.get_unidad_medida_display()}
        for p in Producto.objects.filter(activo=True)
    ])

    if request.method == 'POST':
        items_json = request.POST.get('items_json', '[]')
        try:
            items = json.loads(items_json)
            lineas = services.parsear_items_boleta(items)
            services.ajustar_boleta(boleta, lineas, request.user)
            messages.success(request, f'Boleta #{boleta.numero} corregida correctamente.')
            return redirect('stock:boleta_detalle', boleta.pk)
        except (ValidationError, json.JSONDecodeError) as e:
            mensaje = ' '.join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, mensaje)
            return render(request, 'stock/boleta_ajustar.html', {
                'boleta': boleta, 'productos_json': productos_json, 'items_json': items_json,
            })

    items_json = json.dumps([{
        'producto_id': i.producto_id, 'codigo': i.producto.codigo, 'nombre': i.producto.nombre,
        'unidad_medida': i.producto.get_unidad_medida_display(), 'cantidad': str(i.cantidad),
        'nota': i.nota, 'texto_original': i.texto_original, 'confianza': str(i.confianza) if i.confianza is not None else '',
    } for i in boleta.items.select_related('producto')])
    return render(request, 'stock/boleta_ajustar.html', {
        'boleta': boleta, 'productos_json': productos_json, 'items_json': items_json,
    })


@login_required
def boleta_anular(request, pk):
    if (resp := exigir_permiso(request, 'stock', Role.ADMINISTRADOR)):
        return resp
    boleta = get_object_or_404(Boleta, pk=pk)
    if boleta.estado != Boleta.CONFIRMADA:
        messages.error(request, 'Solo se pueden anular boletas confirmadas.')
        return redirect('stock:boleta_detalle', boleta.pk)

    if request.method == 'POST':
        try:
            services.anular_boleta(boleta, request.user, motivo=request.POST.get('motivo', ''))
            messages.success(request, f'Boleta #{boleta.numero} anulada. Se revirtieron sus movimientos de stock.')
            return redirect('stock:boleta_detalle', boleta.pk)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
    return render(request, 'stock/boleta_anular.html', {'boleta': boleta})


@login_required
def nota_list(request):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    notas = Nota.objects.select_related('usuario').prefetch_related('producto_snapshots', 'movimientos__producto')
    return render(request, 'stock/nota_list.html', {'notas': paginar(request, notas)})


@login_required
def nota_form(request):
    if (resp := exigir_permiso(request, 'stock', Role.CREAR_MODIFICAR)):
        return resp

    if request.method == 'POST':
        form = NotaForm(request.POST)
        productos_json = request.POST.get('productos_json', '[]')
        movimientos_json = request.POST.get('movimientos_json', '[]')
        if form.is_valid():
            try:
                producto_ids = [p['producto_id'] for p in json.loads(productos_json)]
                movimiento_ids = [m['movimiento_id'] for m in json.loads(movimientos_json)]
                services.crear_nota(form.save(commit=False), request.user, producto_ids, movimiento_ids)
                messages.success(request, 'Nota guardada correctamente.')
                return redirect('stock:nota_list')
            except (ValidationError, json.JSONDecodeError, KeyError) as e:
                mensaje = ' '.join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, mensaje)
        return render(request, 'stock/nota_form.html', {
            'form': form, 'productos_json': productos_json, 'movimientos_json': movimientos_json,
        })

    return render(request, 'stock/nota_form.html', {
        'form': NotaForm(), 'productos_json': '[]', 'movimientos_json': '[]',
    })


@login_required
def nota_eliminar(request, pk):
    if (resp := exigir_permiso(request, 'stock', Role.CREAR_MODIFICAR)):
        return resp
    nota = get_object_or_404(Nota, pk=pk)
    if request.method == 'POST':
        nota.delete()
        messages.success(request, 'Nota eliminada.')
    return redirect('stock:nota_list')


@login_required
def exportar_excel(request):
    if (resp := exigir_permiso(request, 'stock', Role.SOLO_VISUALIZACION)):
        return resp
    contenido = services.exportar_stock_excel()
    response = HttpResponse(contenido, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="stock_corralon_nicola_{timezone.localdate()}.xlsx"'
    return response


@login_required
def importar_excel(request):
    if (resp := exigir_permiso(request, 'stock', Role.ADMINISTRADOR)):
        return resp
    if request.method == 'POST':
        form = ImportarExcelForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                resultado = services.importar_stock_excel(form.cleaned_data['archivo'], request.user)
                mensaje = f"Se actualizaron {resultado['actualizados']} producto(s). Sin cambios: {resultado['sin_cambios']}."
                if resultado['no_encontrados']:
                    mensaje += f" No se encontraron {len(resultado['no_encontrados'])} código(s): {', '.join(resultado['no_encontrados'][:10])}"
                messages.success(request, mensaje)
                return redirect('stock:movimiento_list')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
    else:
        form = ImportarExcelForm()
    return render(request, 'stock/importar_excel.html', {'form': form})


@login_required
def ajuste_stock(request):
    if (resp := exigir_permiso(request, 'stock', Role.CREAR_MODIFICAR)):
        return resp
    if request.method == 'POST':
        form = AjusteStockForm(request.POST)
        if form.is_valid():
            try:
                registrar_movimiento(
                    producto=form.cleaned_data['producto'],
                    cantidad=form.cleaned_data['cantidad'],
                    tipo=MovimientoStock.AJUSTE,
                    origen=MovimientoStock.ORIGEN_AJUSTE,
                    usuario=request.user,
                    motivo=form.cleaned_data['motivo'],
                )
                messages.success(request, 'Ajuste de stock registrado.')
                return redirect('stock:movimiento_list')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
    else:
        form = AjusteStockForm()
    return render(request, 'stock/ajuste_stock.html', {'form': form})
