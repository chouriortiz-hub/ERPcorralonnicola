from django.urls import path

from . import views

app_name = 'stock'

urlpatterns = [
    path('categorias/', views.categoria_list, name='categoria_list'),
    path('categorias/nueva/', views.categoria_form, name='categoria_form'),
    path('categorias/<int:pk>/editar/', views.categoria_form, name='categoria_form'),

    path('proveedores/', views.proveedor_list, name='proveedor_list'),
    path('proveedores/nuevo/', views.proveedor_form, name='proveedor_form'),
    path('proveedores/<int:pk>/editar/', views.proveedor_form, name='proveedor_form'),

    path('productos/', views.producto_list, name='producto_list'),
    path('productos/nuevo/', views.producto_form, name='producto_form'),
    path('productos/<int:pk>/editar/', views.producto_form, name='producto_form'),
    path('productos/<int:pk>/toggle/', views.producto_toggle, name='producto_toggle'),

    path('movimientos/', views.movimiento_list, name='movimiento_list'),
    path('ajuste/', views.ajuste_stock, name='ajuste_stock'),
]
