from django.urls import path

from . import views

app_name = 'facturacion'

urlpatterns = [
    path('facturas/', views.factura_list, name='factura_list'),
    path('facturas/<int:pk>/', views.factura_detalle, name='factura_detalle'),
    path('facturas/<int:pk>/imprimir/', views.factura_imprimir, name='factura_imprimir'),

    path('puntos-venta/', views.puntoventa_list, name='puntoventa_list'),
    path('puntos-venta/nuevo/', views.puntoventa_form, name='puntoventa_form'),
    path('puntos-venta/<int:pk>/editar/', views.puntoventa_form, name='puntoventa_form'),
]
