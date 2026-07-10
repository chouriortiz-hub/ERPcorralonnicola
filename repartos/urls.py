from django.urls import path

from . import views

app_name = 'repartos'

urlpatterns = [
    path('vehiculos/', views.vehiculo_list, name='vehiculo_list'),
    path('vehiculos/nuevo/', views.vehiculo_form, name='vehiculo_form'),
    path('vehiculos/<int:pk>/editar/', views.vehiculo_form, name='vehiculo_form'),

    path('', views.reparto_list, name='reparto_list'),
    path('calendario/', views.calendario, name='calendario'),
    path('dia/<str:fecha>/', views.reparto_dia, name='reparto_dia'),
    path('pedidos-disponibles/', views.pedidos_disponibles, name='pedidos_disponibles'),
    path('nuevo/', views.reparto_form, name='reparto_form'),
    path('<int:pk>/', views.reparto_detalle, name='reparto_detalle'),
    path('pedidos-salida/<int:pk>/', views.repartopedido_salida, name='repartopedido_salida'),
    path('pedidos-entrega/<int:pk>/', views.repartopedido_entrega, name='repartopedido_entrega'),
    path('api/pedidos-pendientes/', views.buscar_pedidos_pendientes, name='buscar_pedidos_pendientes'),
]
