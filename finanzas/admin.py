from django.contrib import admin

from .models import CierreCaja, Journal


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'cuenta_codigo', 'debe', 'haber', 'referencia_tipo', 'referencia_id')
    list_filter = ('cuenta_codigo', 'referencia_tipo')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CierreCaja)
class CierreCajaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'estado', 'fecha_apertura', 'monto_apertura', 'fecha_cierre', 'efectivo_contado', 'diferencia')
    list_filter = ('estado', 'usuario')
