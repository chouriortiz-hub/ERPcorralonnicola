"""Vistas de CORE: dashboard general, búsqueda global y administración de
usuarios/roles (reservada a superusuarios, ya que reemplaza lo que antes
se gestionaba desde el Django Admin)."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from compras.models import Compra
from facturacion.models import Factura
from repartos.models import Reparto
from stock.models import Producto
from ventas.models import Cliente, Pedido

from .forms import RoleForm, UsuarioForm
from .models import Role, User
from .permissions import get_effective_permissions
from .views_utils import paginar


@login_required
def dashboard(request):
    permisos = get_effective_permissions(request.user)
    hoy = date.today()
    contexto = {}

    if permisos['ventas'] > 0:
        contexto['pedidos_pendientes'] = Pedido.objects.filter(estado='PENDIENTE').count()
        contexto['pedidos_mes'] = Pedido.objects.filter(fecha__year=hoy.year, fecha__month=hoy.month).count()
        contexto['ultimos_pedidos'] = Pedido.objects.select_related('cliente').order_by('-fecha')[:5]

    if permisos['facturacion'] > 0:
        facturas_mes = Factura.objects.filter(estado='AUTORIZADA', fecha__year=hoy.year, fecha__month=hoy.month)
        contexto['total_facturado_mes'] = facturas_mes.aggregate(total=Sum('total'))['total'] or 0
        contexto['ultimas_facturas'] = Factura.objects.select_related('cliente').order_by('-fecha')[:5]

    if permisos['stock'] > 0:
        productos_activos = Producto.objects.filter(activo=True)
        contexto['productos_activos'] = productos_activos.count()
        contexto['productos_bajo_stock'] = productos_activos.filter(
            descuenta_stock=True, stock_actual__lte=F('stock_minimo'),
        ).count()

    if permisos['compras'] > 0:
        contexto['compras_mes'] = Compra.objects.filter(
            estado='CONFIRMADA', creado__year=hoy.year, creado__month=hoy.month,
        ).count()

    if permisos['repartos'] > 0:
        contexto['repartos_hoy'] = Reparto.objects.filter(
            fecha=hoy, estado__in=['PROGRAMADO', 'EN_CURSO'],
        ).count()

    return render(request, 'core/dashboard.html', contexto)


@login_required
def buscar_global(request):
    q = request.GET.get('q', '').strip()
    permisos = get_effective_permissions(request.user)
    resultados = {'clientes': [], 'productos': [], 'pedidos': []}

    if q:
        if permisos['ventas'] > 0:
            resultados['clientes'] = Cliente.objects.filter(nombre__icontains=q)[:10]
            pedido_qs = Pedido.objects.select_related('cliente')
            resultados['pedidos'] = (
                pedido_qs.filter(pk=q) if q.isdigit() else pedido_qs.filter(cliente__nombre__icontains=q)
            )[:10]
        if permisos['stock'] > 0:
            resultados['productos'] = Producto.objects.filter(
                Q(nombre__icontains=q) | Q(codigo__icontains=q),
            )[:10]

    return render(request, 'core/buscar_global.html', {'q': q, 'resultados': resultados})


@login_required
def usuario_list(request):
    if not request.user.is_superuser:
        messages.error(request, 'Solo un administrador del sistema puede gestionar usuarios.')
        return redirect('core:dashboard')

    q = request.GET.get('q', '').strip()
    usuarios = User.objects.all().order_by('username')
    if q:
        usuarios = usuarios.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))

    return render(request, 'core/usuario_list.html', {'usuarios': paginar(request, usuarios), 'q': q})


@login_required
def usuario_form(request, pk=None):
    if not request.user.is_superuser:
        messages.error(request, 'Solo un administrador del sistema puede gestionar usuarios.')
        return redirect('core:dashboard')

    usuario = get_object_or_404(User, pk=pk) if pk else None
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario guardado correctamente.')
            return redirect('core:usuario_list')
    else:
        form = UsuarioForm(instance=usuario)

    return render(request, 'core/usuario_form.html', {'form': form, 'usuario': usuario})


@login_required
def usuario_toggle(request, pk):
    if not request.user.is_superuser:
        messages.error(request, 'Solo un administrador del sistema puede gestionar usuarios.')
        return redirect('core:dashboard')

    usuario = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        usuario.activo = not usuario.activo
        usuario.is_active = usuario.activo
        usuario.save(update_fields=['activo', 'is_active'])
        messages.success(request, f'Usuario {"activado" if usuario.activo else "desactivado"}.')
    return redirect('core:usuario_list')


@login_required
def role_list(request):
    if not request.user.is_superuser:
        messages.error(request, 'Solo un administrador del sistema puede gestionar roles.')
        return redirect('core:dashboard')
    return render(request, 'core/role_list.html', {'roles': Role.objects.all().order_by('name')})


@login_required
def role_form(request, pk=None):
    if not request.user.is_superuser:
        messages.error(request, 'Solo un administrador del sistema puede gestionar roles.')
        return redirect('core:dashboard')

    role = get_object_or_404(Role, pk=pk) if pk else None
    if request.method == 'POST':
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rol guardado correctamente.')
            return redirect('core:role_list')
    else:
        form = RoleForm(instance=role)

    return render(request, 'core/role_form.html', {'form': form, 'role': role})
