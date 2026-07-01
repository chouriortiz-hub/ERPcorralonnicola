from django.contrib import admin, messages

from .models import Reparto, RepartoPedido, Vehiculo


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ('patente', 'descripcion', 'activo')


class RepartoPedidoInline(admin.TabularInline):
    model = RepartoPedido
    extra = 0


@admin.register(Reparto)
class RepartoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'chofer', 'vehiculo', 'estado')
    list_filter = ('estado', 'fecha')
    inlines = [RepartoPedidoInline]


@admin.register(RepartoPedido)
class RepartoPedidoAdmin(admin.ModelAdmin):
    list_display = ('reparto', 'pedido', 'orden', 'direccion_entrega', 'estado_entrega')
    list_filter = ('estado_entrega',)
    actions = ['marcar_entregados']

    def marcar_entregados(self, request, queryset):
        for rp in queryset:
            try:
                rp.marcar_entregado()
            except Exception as e:
                self.message_user(request, str(e), level=messages.ERROR)
    marcar_entregados.short_description = 'Marcar como entregado'
