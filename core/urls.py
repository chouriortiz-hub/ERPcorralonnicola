from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='core:login'), name='logout'),
    path('buscar/', views.buscar_global, name='buscar_global'),

    path('usuarios/', views.usuario_list, name='usuario_list'),
    path('usuarios/nuevo/', views.usuario_form, name='usuario_form'),
    path('usuarios/<int:pk>/editar/', views.usuario_form, name='usuario_form'),
    path('usuarios/<int:pk>/toggle/', views.usuario_toggle, name='usuario_toggle'),

    path('roles/', views.role_list, name='role_list'),
    path('roles/nuevo/', views.role_form, name='role_form'),
    path('roles/<int:pk>/editar/', views.role_form, name='role_form'),
]
