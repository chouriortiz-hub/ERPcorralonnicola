from django.db import migrations


def actualizar_venta_mostrador(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    Role.objects.update_or_create(
        name='Venta Mostrador',
        defaults=dict(
            stock_perm=1, ventas_perm=2, compras_perm=0,
            facturacion_perm=2, repartos_perm=0, finanzas_perm=2,
        ),
    )


def revertir(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    Role.objects.filter(name='Venta Mostrador').update(facturacion_perm=0)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(actualizar_venta_mostrador, revertir),
    ]
