"""
Comando de management para dejar el ERP listo para usar con datos base:
roles típicos del corralón y el punto de venta principal.

Uso:
    python manage.py datos_iniciales
"""
from django.core.management.base import BaseCommand

from core.models import Role, UserRole
from facturacion.models import PuntoVenta
from stock.models import Categoria

# Nombres anteriores de roles que este comando reemplaza por los 3 roles de
# negocio (Administrador / Venta Mostrador / Reparto). Se resuelven en el
# propio comando para que nunca convivan dos roles equivalentes en la base:
# si existe el rol viejo se renombra (o se fusiona, si el nuevo ya existe).
RENOMBRES_LEGACY = {
    'Vendedor Mostrador': 'Venta Mostrador',
    'Chofer': 'Reparto',
}


class Command(BaseCommand):
    help = 'Carga roles, categorías y punto de venta iniciales del Corralón Nicola.'

    def _resolver_roles_legacy(self):
        for nombre_viejo, nombre_nuevo in RENOMBRES_LEGACY.items():
            viejo = Role.objects.filter(name=nombre_viejo).first()
            if not viejo:
                continue
            nuevo = Role.objects.filter(name=nombre_nuevo).first()
            if nuevo:
                # Los dos roles existen (ej. quedaron de una corrida anterior
                # del comando): pasar los usuarios del viejo al nuevo y
                # eliminar el viejo, sin dejar roles duplicados.
                ya_tienen_el_nuevo = UserRole.objects.filter(role=nuevo).values('user')
                UserRole.objects.filter(role=viejo).exclude(user__in=ya_tienen_el_nuevo).update(role=nuevo)
                viejo.delete()
                self.stdout.write(self.style.WARNING(
                    f'Rol legacy "{nombre_viejo}" fusionado en "{nombre_nuevo}" y eliminado.'
                ))
            else:
                viejo.name = nombre_nuevo
                viejo.save(update_fields=['name'])
                self.stdout.write(self.style.WARNING(
                    f'Rol legacy "{nombre_viejo}" renombrado a "{nombre_nuevo}".'
                ))

    def handle(self, *args, **options):
        self._resolver_roles_legacy()

        roles = [
            # Acceso total a los 6 módulos: además de operar todo, puede dar
            # de alta/baja usuarios de Venta Mostrador y Reparto (ver
            # core.permissions.es_administrador).
            dict(name='Administrador', stock_perm=3, ventas_perm=3, compras_perm=3,
                 facturacion_perm=3, repartos_perm=3, finanzas_perm=3),
            # Pedidos y presupuestos (ventas) con facturación incluida, stock
            # en modo lectura (sin poder editar/eliminar/agregar) y finanzas
            # para poder abrir/cerrar su caja y consultar el libro diario.
            dict(name='Venta Mostrador', stock_perm=1, ventas_perm=2, compras_perm=0,
                 facturacion_perm=2, repartos_perm=0, finanzas_perm=2),
            dict(name='Encargado de Depósito', stock_perm=2, ventas_perm=0, compras_perm=2,
                 facturacion_perm=0, repartos_perm=0, finanzas_perm=0),
            # Solo repartos: ver el calendario de pedidos agendados y marcar
            # la salida (total o parcial, por producto) de la mercadería.
            dict(name='Reparto', stock_perm=0, ventas_perm=0, compras_perm=0,
                 facturacion_perm=0, repartos_perm=2, finanzas_perm=0),
        ]
        for r in roles:
            role, creado = Role.objects.update_or_create(name=r['name'], defaults=r)
            self.stdout.write(self.style.SUCCESS(f'{"Creado" if creado else "Actualizado"}: Rol "{role.name}"'))

        pv, creado = PuntoVenta.objects.get_or_create(numero=1, defaults={'nombre': 'Mostrador Corralón Nicola'})
        self.stdout.write(self.style.SUCCESS(f'{"Creado" if creado else "Ya existía"}: {pv}'))

        categorias = ['Cemento y Áridos', 'Hierros y Mallas', 'Ladrillos y Bloques',
                      'Pinturas', 'Sanitarios', 'Herramientas', 'Fletes y Servicios']
        for nombre in categorias:
            cat, creado = Categoria.objects.get_or_create(nombre=nombre)
            self.stdout.write(self.style.SUCCESS(f'{"Creada" if creado else "Ya existía"}: Categoría "{cat.nombre}"'))

        self.stdout.write(self.style.SUCCESS('\nListo. Ahora creá tu superusuario con: python manage.py createsuperuser'))
