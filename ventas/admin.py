from django.contrib import admin, messages

from .models import Cliente, Pedido, PedidoLinea, Presupuesto, PresupuestoLinea


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cuit_dni', 'condicion_iva', 'telefono', 'activo')
    search_fields = ('nombre', 'cuit_dni')


class PresupuestoLineaInline(admin.TabularInline):
    model = PresupuestoLinea
    extra = 1


@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'vendedor', 'fecha', 'estado', 'total')
    list_filter = ('estado',)
    inlines = [PresupuestoLineaInline]
    actions = ['convertir_a_pedido']

    def convertir_a_pedido(self, request, queryset):
        for p in queryset:
            try:
                p.convertir_a_pedido(usuario=request.user)
            except Exception as e:
                self.message_user(request, f'Presupuesto #{p.id}: {e}', level=messages.ERROR)
    convertir_a_pedido.short_description = 'Convertir a Pedido'


class PedidoLineaInline(admin.TabularInline):
    model = PedidoLinea
    extra = 1
    fields = ('producto', 'cantidad', 'precio_unitario', 'sale_con_reparto', 'stock_descontado', 'cantidad_salida')
    readonly_fields = ('stock_descontado', 'cantidad_salida')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'vendedor', 'fecha', 'estado', 'tipo_entrega', 'fecha_entrega_estimada', 'total')
    list_filter = ('estado', 'tipo_entrega')
    inlines = [PedidoLineaInline]
    actions = ['confirmar_pedidos']

    def confirmar_pedidos(self, request, queryset):
        for pedido in queryset:
            try:
                pedido.confirmar(usuario=request.user)
            except Exception as e:
                self.message_user(request, f'Pedido #{pedido.id}: {e}', level=messages.ERROR)
    confirmar_pedidos.short_description = 'Confirmar pedidos seleccionados (impacta stock)'
