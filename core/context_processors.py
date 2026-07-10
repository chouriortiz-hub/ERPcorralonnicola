"""Contexto disponible en todos los templates: qué ve cada usuario en el sidebar."""
from .permissions import es_administrador, get_effective_permissions


def permisos(request):
    return {
        'permisos_modulos': get_effective_permissions(request.user),
        'es_admin_sistema': es_administrador(request.user),
    }
