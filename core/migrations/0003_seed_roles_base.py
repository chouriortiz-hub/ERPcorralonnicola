from django.db import migrations

ROLES_BASE = [
    dict(name='Administrador', stock_perm=3, ventas_perm=3, compras_perm=3,
         facturacion_perm=3, repartos_perm=3, finanzas_perm=3),
    dict(name='Venta Mostrador', stock_perm=1, ventas_perm=2, compras_perm=0,
         facturacion_perm=2, repartos_perm=0, finanzas_perm=2),
    dict(name='Encargado de Depósito', stock_perm=2, ventas_perm=0, compras_perm=2,
         facturacion_perm=0, repartos_perm=0, finanzas_perm=0),
    dict(name='Reparto', stock_perm=0, ventas_perm=0, compras_perm=0,
         facturacion_perm=0, repartos_perm=2, finanzas_perm=0),
]


def sembrar_roles(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    for r in ROLES_BASE:
        Role.objects.get_or_create(name=r['name'], defaults=r)


def revertir(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_venta_mostrador_puede_facturar'),
    ]

    operations = [
        migrations.RunPython(sembrar_roles, revertir),
    ]
