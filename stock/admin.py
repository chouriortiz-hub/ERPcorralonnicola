from django.contrib import admin

from .models import Categoria, MovimientoStock, Producto, Proveedor


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    search_fields = ('nombre',)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cuit', 'telefono', 'activo')
    search_fields = ('nombre', 'cuit')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        'codigo', 'nombre', 'categoria', 'stock_actual', 'stock_minimo',
        'pmp', 'precio_venta', 'descuenta_stock', 'activo',
    )
    list_filter = ('categoria', 'descuenta_stock', 'activo')
    search_fields = ('codigo', 'nombre')
    list_editable = ('descuenta_stock', 'precio_venta')


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'producto', 'tipo', 'cantidad', 'stock_resultante', 'origen', 'usuario')
    list_filter = ('tipo', 'origen', 'fecha')
    search_fields = ('producto__codigo', 'producto__nombre')
    readonly_fields = [f.name for f in MovimientoStock._meta.fields]

    def has_add_permission(self, request):
        return False  # los movimientos se crean solo vía registrar_movimiento()

    def has_change_permission(self, request, obj=None):
        return False
