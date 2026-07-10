from django.db import migrations, models


def backfill_cantidad_salida(apps, schema_editor):
    """Líneas de reparto ya marcadas como 'stock_descontado=True' bajo el
    esquema anterior (todo o nada) representaban una salida completa:
    reflejarlo en cantidad_salida para no perder ese historial."""
    PedidoLinea = apps.get_model('ventas', 'PedidoLinea')
    PedidoLinea.objects.filter(
        sale_con_reparto=True, stock_descontado=True, cantidad_salida=0,
    ).update(cantidad_salida=models.F('cantidad'))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0003_pedidolinea_cantidad_salida_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_cantidad_salida, noop),
    ]
