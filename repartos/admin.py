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
    actions = ['marcar_salida_action']

    def marcar_salida_action(self, request, queryset):
        for reparto in queryset:
            try:
                reparto.marcar_salida(usuario=request.user)
            except Exception as e:
                self.message_user(request, f'Reparto #{reparto.id}: {e}', level=messages.ERROR)
    marcar_salida_action.short_description = 'Marcar salida a reparto (descuenta stock pendiente)'


@admin.register(RepartoPedido)
class RepartoPedidoAdmin(admin.ModelAdmin):
    list_display = ('reparto', 'pedido', 'orden', 'direccion_entrega', 'estado_salida', 'estado_entrega')
    list_filter = ('estado_salida', 'estado_entrega')
    actions = ['marcar_salieron', 'marcar_entregados']

    def marcar_salieron(self, request, queryset):
        for rp in queryset:
            try:
                rp.marcar_salida(usuario=request.user)
            except Exception as e:
                self.message_user(request, str(e), level=messages.ERROR)
    marcar_salieron.short_description = 'Marcar salida del depósito (descuenta stock pendiente)'

    def marcar_entregados(self, request, queryset):
        for rp in queryset:
            try:
                rp.marcar_entregado()
            except Exception as e:
                self.message_user(request, str(e), level=messages.ERROR)
    marcar_entregados.short_description = 'Marcar como entregado'
