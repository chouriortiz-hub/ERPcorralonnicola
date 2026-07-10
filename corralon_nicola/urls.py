"""
URL configuration for corralon_nicola project.

El frontend a medida (`core`, `stock`, `ventas`, `compras`, `facturacion`,
`repartos`, `finanzas`) es la interfaz principal del sistema. El admin de
Django queda montado en `/admin/` solo como respaldo técnico, sin enlaces
desde la interfaz nueva.
"""
from django.conf import settings
from django.conf.urls.static import static
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

# Se sirven siempre por Django (no solo en DEBUG): este proyecto no tiene un
# reverse proxy propio para estáticos de media y el volumen de adjuntos de
# boletas es bajo. Si el tráfico crece, migrar a un storage externo (S3, etc.).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
