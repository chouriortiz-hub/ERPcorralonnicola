from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Role
from core.views_utils import exigir_permiso, paginar

from .forms import AjusteStockForm, CategoriaForm, ProductoForm, ProveedorForm
from .models import Categoria, MovimientoStock, Producto, Proveedor, registrar_movimiento


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
    movimientos = MovimientoStock.objects.select_related('producto', 'usuario')
    if q:
        movimientos = movimientos.filter(Q(producto__codigo__icontains=q) | Q(producto__nombre__icontains=q))
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)
    return render(request, 'stock/movimiento_list.html', {
        'movimientos': paginar(request, movimientos),
        'q': q, 'tipo': tipo,
        'tipos': MovimientoStock.TIPO_CHOICES,
    })


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
