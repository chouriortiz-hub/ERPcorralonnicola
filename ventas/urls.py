from django.urls import path

from . import views

app_name = 'ventas'

urlpatterns = [
    path('pedidos/nuevo/', views.nuevo_pedido, name='nuevo_pedido'),
    path('api/productos/', views.buscar_productos, name='buscar_productos'),
    path('api/clientes/', views.buscar_clientes, name='buscar_clientes'),
    path('presupuestos/<int:pk>/imprimir/', views.presupuesto_imprimir, name='presupuesto_imprimir'),

    path('clientes/', views.cliente_list, name='cliente_list'),
    path('clientes/nuevo/', views.cliente_form, name='cliente_form'),
    path('clientes/<int:pk>/editar/', views.cliente_form, name='cliente_form'),
    path('clientes/<int:pk>/toggle/', views.cliente_toggle, name='cliente_toggle'),

    path('presupuestos/', views.presupuesto_list, name='presupuesto_list'),
    path('presupuestos/<int:pk>/', views.presupuesto_detalle, name='presupuesto_detalle'),

    path('pedidos/', views.pedido_list, name='pedido_list'),
    path('pedidos/<int:pk>/', views.pedido_detalle, name='pedido_detalle'),
]
