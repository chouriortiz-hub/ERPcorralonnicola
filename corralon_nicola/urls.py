"""
URL configuration for corralon_nicola project.

El frontend a medida (`core`, `stock`, `ventas`, `compras`, `facturacion`,
`repartos`, `finanzas`) es la interfaz principal del sistema. El admin de
Django queda montado en `/admin/` solo como respaldo técnico, sin enlaces
desde la interfaz nueva.
"""
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Corralón Nicola — Sistema de Gestión'
admin.site.site_title = 'Corralón Nicola ERP'
admin.site.index_title = 'Panel de gestión'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('stock/', include('stock.urls')),
    path('ventas/', include('ventas.urls')),
    path('compras/', include('compras.urls')),
    path('facturacion/', include('facturacion.urls')),
    path('repartos/', include('repartos.urls')),
    path('finanzas/', include('finanzas.urls')),
    path('comunicados/', include('comunicados.urls')),
]
