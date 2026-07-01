"""
Lógica de Consolidación de Permisos (Senior Insight de la guía técnica).

Un mismo usuario puede tener varios roles (ej: es Vendedor Y también
Encargado de Depósito). El permiso EFECTIVO de un usuario sobre un módulo
es el máximo valor entre todos sus roles.

Esta es la función central que consultan todos los módulos del ERP antes
de permitir una acción (ver stock, cargar una compra, facturar, etc.),
por lo que es uno de los puntos que interconecta a todo el sistema.
"""
from functools import wraps

from django.core.exceptions import PermissionDenied

from .models import Role, UserRole

MODULOS = ['stock', 'ventas', 'compras', 'facturacion', 'repartos', 'finanzas']


def get_effective_permissions(user):
    """Devuelve un dict {modulo: nivel_max} con el permiso efectivo del usuario."""
    perms = {m: Role.SIN_ACCESO for m in MODULOS}
    if not user.is_authenticated:
        return perms
    if user.is_superuser:
        return {m: Role.ADMINISTRADOR for m in MODULOS}

    user_roles = UserRole.objects.filter(user=user).select_related('role')
    for ur in user_roles:
        for modulo in MODULOS:
            campo = f'{modulo}_perm'
            perms[modulo] = max(perms[modulo], getattr(ur.role, campo))
    return perms


def tiene_permiso(user, modulo, nivel_minimo=Role.SOLO_VISUALIZACION):
    """Chequeo puntual: ¿el usuario tiene al menos `nivel_minimo` en `modulo`?"""
    perms = get_effective_permissions(user)
    return perms.get(modulo, Role.SIN_ACCESO) >= nivel_minimo


def requiere_permiso(modulo, nivel_minimo=Role.SOLO_VISUALIZACION):
    """Decorador de vistas: exige permiso consolidado sobre un módulo."""
    def decorador(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not tiene_permiso(request.user, modulo, nivel_minimo):
                raise PermissionDenied(
                    f'No tenés permiso suficiente sobre el módulo "{modulo}".'
                )
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorador
