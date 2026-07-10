from django.contrib import admin

from core.permissions import es_administrador

from .models import Aviso


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'activo', 'fecha_vencimiento', 'creado_por', 'fecha_creacion')
    list_filter = ('tipo', 'activo')
    search_fields = ('titulo', 'mensaje')
    filter_horizontal = ('productos',)

    def has_add_permission(self, request):
        return es_administrador(request.user)

    def has_change_permission(self, request, obj=None):
        return es_administrador(request.user)

    def has_delete_permission(self, request, obj=None):
        return es_administrador(request.user)
