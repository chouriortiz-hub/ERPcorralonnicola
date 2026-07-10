from django.urls import path

from . import views

app_name = 'finanzas'

urlpatterns = [
    path('', views.libro_diario, name='libro_diario'),
    path('caja/', views.caja_actual, name='caja_actual'),
    path('caja/historial/', views.caja_list, name='caja_list'),
    path('caja/<int:pk>/', views.caja_detalle, name='caja_detalle'),
]
