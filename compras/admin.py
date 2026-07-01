from django.contrib import admin
from django.contrib import messages

from .models import Compra, CompraLinea


class CompraLineaInline(admin.TabularInline):
    model = CompraLinea
    extra = 1


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'proveedor', 'fecha', 'estado', 'total', 'usuario')
    list_filter = ('estado', 'proveedor')
    inlines = [CompraLineaInline]
    actions = ['confirmar_compras']

    def confirmar_compras(self, request, queryset):
        for compra in queryset:
            try:
                compra.confirmar(usuario=request.user)
            except Exception as e:
                self.message_user(request, f'Compra #{compra.id}: {e}', level=messages.ERROR)
    confirmar_compras.short_description = 'Confirmar compras seleccionadas (impacta stock)'
