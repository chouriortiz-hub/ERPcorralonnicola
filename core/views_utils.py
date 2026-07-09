"""Helpers chicos compartidos por las vistas de listado/CRUD de todas las apps."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect

from .permissions import tiene_permiso


def paginar(request, queryset, por_pagina=20):
    paginator = Paginator(queryset, por_pagina)
    return paginator.get_page(request.GET.get('page'))


def exigir_permiso(request, modulo, nivel_minimo):
    """Si el usuario no tiene el nivel pedido, carga un mensaje de error y
    devuelve un redirect al dashboard. Si tiene permiso, devuelve None."""
    if not tiene_permiso(request.user, modulo, nivel_minimo):
        messages.error(request, 'No tenés permiso suficiente para acceder a esta sección.')
        return redirect('core:dashboard')
    return None
