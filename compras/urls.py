from django.urls import path

from . import views

app_name = 'compras'

urlpatterns = [
    path('', views.compra_list, name='compra_list'),
    path('nueva/', views.compra_form, name='compra_form'),
    path('<int:pk>/', views.compra_detalle, name='compra_detalle'),
    path('api/proveedores/', views.buscar_proveedores, name='buscar_proveedores'),
]
