from django.urls import path

from . import views

app_name = 'stock'

urlpatterns = [
    path('dashboard/', views.dashboard_stock, name='dashboard'),

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
    path('productos/buscar/', views.buscar_productos, name='buscar_productos'),

    path('movimientos/', views.movimiento_list, name='movimiento_list'),
    path('movimientos/buscar/', views.buscar_movimientos, name='buscar_movimientos'),
    path('ajuste/', views.ajuste_stock, name='ajuste_stock'),

    path('boletas/', views.boleta_list, name='boleta_list'),
    path('boletas/nueva/', views.boleta_form, name='boleta_form'),
    path('boletas/<int:pk>/', views.boleta_detalle, name='boleta_detalle'),
    path('boletas/<int:pk>/ajustar/', views.boleta_ajustar, name='boleta_ajustar'),
    path('boletas/<int:pk>/anular/', views.boleta_anular, name='boleta_anular'),

    path('notas/', views.nota_list, name='nota_list'),
    path('notas/nueva/', views.nota_form, name='nota_form'),
    path('notas/<int:pk>/eliminar/', views.nota_eliminar, name='nota_eliminar'),

    path('excel/exportar/', views.exportar_excel, name='exportar_excel'),
    path('excel/importar/', views.importar_excel, name='importar_excel'),
]
