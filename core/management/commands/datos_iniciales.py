"""
Comando de management para dejar el ERP listo para usar con datos base:
roles típicos del corralón y el punto de venta principal.

Uso:
    python manage.py datos_iniciales
"""
from django.core.management.base import BaseCommand

from core.models import Role
from facturacion.models import PuntoVenta
from stock.models import Categoria


class Command(BaseCommand):
    help = 'Carga roles, categorías y punto de venta iniciales del Corralón Nicola.'

    def handle(self, *args, **options):
        roles = [
            dict(name='Administrador', stock_perm=3, ventas_perm=3, compras_perm=3,
                 facturacion_perm=3, repartos_perm=3, finanzas_perm=3),
            dict(name='Vendedor Mostrador', stock_perm=1, ventas_perm=2, compras_perm=0,
                 facturacion_perm=2, repartos_perm=1, finanzas_perm=0),
            dict(name='Encargado de Depósito', stock_perm=2, ventas_perm=0, compras_perm=2,
                 facturacion_perm=0, repartos_perm=0, finanzas_perm=0),
            dict(name='Chofer', stock_perm=0, ventas_perm=0, compras_perm=0,
                 facturacion_perm=0, repartos_perm=2, finanzas_perm=0),
        ]
        for r in roles:
            role, creado = Role.objects.get_or_create(name=r['name'], defaults=r)
            self.stdout.write(self.style.SUCCESS(f'{"Creado" if creado else "Ya existía"}: Rol "{role.name}"'))

        pv, creado = PuntoVenta.objects.get_or_create(numero=1, defaults={'nombre': 'Mostrador Corralón Nicola'})
        self.stdout.write(self.style.SUCCESS(f'{"Creado" if creado else "Ya existía"}: {pv}'))

        categorias = ['Cemento y Áridos', 'Hierros y Mallas', 'Ladrillos y Bloques',
                      'Pinturas', 'Sanitarios', 'Herramientas', 'Fletes y Servicios']
        for nombre in categorias:
            cat, creado = Categoria.objects.get_or_create(nombre=nombre)
            self.stdout.write(self.style.SUCCESS(f'{"Creada" if creado else "Ya existía"}: Categoría "{cat.nombre}"'))

        self.stdout.write(self.style.SUCCESS('\nListo. Ahora creá tu superusuario con: python manage.py createsuperuser'))
