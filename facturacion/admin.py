from django.contrib import admin

from .models import Factura, FacturaLinea, PuntoVenta


@admin.register(PuntoVenta)
class PuntoVentaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'nombre')


class FacturaLineaInline(admin.TabularInline):
    model = FacturaLinea
    extra = 0


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'tipo_comprobante', 'punto_venta', 'numero', 'cliente',
        'total', 'estado', 'cae', 'cae_vencimiento', 'fecha',
    )
    list_filter = ('estado', 'tipo_comprobante', 'punto_venta')
    search_fields = ('cliente__nombre', 'cae', 'numero')
    inlines = [FacturaLineaInline]
    readonly_fields = ('cae', 'cae_vencimiento', 'numero', 'subtotal', 'iva', 'total')
