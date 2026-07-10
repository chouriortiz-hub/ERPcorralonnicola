from django.urls import path

from . import views

app_name = 'comunicados'

urlpatterns = [
    path('', views.aviso_list, name='aviso_list'),
    path('nuevo/', views.aviso_form, name='aviso_form'),
    path('<int:pk>/editar/', views.aviso_form, name='aviso_form'),
    path('<int:pk>/toggle/', views.aviso_toggle, name='aviso_toggle'),
]
