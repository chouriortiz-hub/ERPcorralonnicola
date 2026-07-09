"""Contexto disponible en todos los templates: qué ve cada usuario en el sidebar."""
from .permissions import get_effective_permissions


def permisos(request):
    return {
        'permisos_modulos': get_effective_permissions(request.user),
        'es_admin_sistema': request.user.is_authenticated and request.user.is_superuser,
    }
