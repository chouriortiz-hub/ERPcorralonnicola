from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import User
from stock.models import Categoria, Producto
from ventas.models import Cliente, Pedido, PedidoLinea

from .models import Reparto, RepartoPedido, Vehiculo


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class RepartoFlowTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser(username='admin', password='x', email='a@a.com')
        self.cliente = Cliente.objects.create(nombre='Cliente Test')
        categoria = Categoria.objects.create(nombre='Materiales')
        self.producto = Producto.objects.create(
            codigo='P1', nombre='Cemento', categoria=categoria,
            descuenta_stock=True, stock_actual=100,
        )
        self.vehiculo = Vehiculo.objects.create(patente='AA111BB')
        self.pedido = Pedido.objects.create(cliente=self.cliente, vendedor=self.usuario)
        PedidoLinea.objects.create(
            pedido=self.pedido, producto=self.producto, cantidad=10, precio_unitario=100, sale_con_reparto=True,
        )
        self.pedido.actualizar_tipo_entrega()
        self.pedido.confirmar(usuario=self.usuario)

    def test_confirmar_no_descuenta_lineas_con_reparto(self):
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 100)
        self.assertTrue(self.pedido.tiene_lineas_pendientes_reparto)

    def test_marcar_salida_por_pedido_descuenta_stock_y_no_afecta_otros_pedidos(self):
        reparto = Reparto.objects.create(fecha=date.today(), chofer=self.usuario, vehiculo=self.vehiculo)
        rp = reparto.agregar_pedido(self.pedido)

        otro_pedido = Pedido.objects.create(cliente=self.cliente, vendedor=self.usuario)
        PedidoLinea.objects.create(
            pedido=otro_pedido, producto=self.producto, cantidad=5, precio_unitario=100, sale_con_reparto=True,
        )
        otro_pedido.actualizar_tipo_entrega()
        otro_pedido.confirmar(usuario=self.usuario)
        rp_otro = reparto.agregar_pedido(otro_pedido)

        rp.marcar_salida(usuario=self.usuario)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 90)  # solo se descontó el pedido marcado
        rp.refresh_from_db()
        self.assertEqual(rp.estado_salida, RepartoPedido.SALIO)
        rp_otro.refresh_from_db()
        self.assertEqual(rp_otro.estado_salida, RepartoPedido.PENDIENTE)

        reparto.refresh_from_db()
        self.assertEqual(reparto.estado, Reparto.EN_CURSO)

    def test_no_se_puede_entregar_antes_de_salir(self):
        reparto = Reparto.objects.create(fecha=date.today(), chofer=self.usuario, vehiculo=self.vehiculo)
        rp = reparto.agregar_pedido(self.pedido)
        with self.assertRaises(ValidationError):
            rp.marcar_entregado()

        rp.marcar_salida(usuario=self.usuario)
        rp.marcar_entregado()
        rp.refresh_from_db()
        self.assertEqual(rp.estado_entrega, RepartoPedido.ENTREGADO)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.ENTREGADO)

    def test_marcar_no_salio_no_descuenta_stock(self):
        reparto = Reparto.objects.create(fecha=date.today(), chofer=self.usuario, vehiculo=self.vehiculo)
        rp = reparto.agregar_pedido(self.pedido)
        rp.marcar_no_salio(motivo='Camión lleno')
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 100)
        self.assertEqual(rp.estado_salida, RepartoPedido.NO_SALIO)

    def test_calendario_y_vista_de_dia(self):
        reparto = Reparto.objects.create(fecha=date.today(), chofer=self.usuario, vehiculo=self.vehiculo)
        rp = reparto.agregar_pedido(self.pedido)
        self.client.force_login(self.usuario)

        resp = self.client.get(reverse('repartos:calendario'))
        self.assertEqual(resp.status_code, 200)
        hoy_info = next(
            c for semana in resp.context['semanas'] for c in semana if c and c['numero'] == date.today().day
        )
        self.assertEqual(hoy_info['total'], 1)
        self.assertEqual(hoy_info['pendientes'], 1)

        url_dia = reverse('repartos:reparto_dia', kwargs={'fecha': date.today().isoformat()})
        resp = self.client.get(url_dia)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Cemento')
        self.assertContains(resp, '10')

        resp = self.client.post(url_dia, {'reparto_pedido_id': rp.pk, 'accion': 'salio'})
        self.assertRedirects(resp, url_dia)
        rp.refresh_from_db()
        self.assertEqual(rp.estado_salida, RepartoPedido.SALIO)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 90)

    def test_nuevo_reparto_muestra_y_asigna_pedidos_disponibles(self):
        self.client.force_login(self.usuario)

        resp = self.client.get(reverse('repartos:reparto_form'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.pedido, list(resp.context['pedidos_disponibles']))
        self.assertContains(resp, 'Cemento')

        resp = self.client.post(reverse('repartos:reparto_form'), {
            'fecha': date.today().isoformat(),
            'chofer': self.usuario.pk,
            'vehiculo': self.vehiculo.pk,
            'observaciones': '',
            'pedidos_seleccionados': [self.pedido.pk],
        })
        reparto = Reparto.objects.latest('id')
        self.assertRedirects(resp, reverse('repartos:reparto_detalle', kwargs={'pk': reparto.pk}))
        self.assertTrue(RepartoPedido.objects.filter(reparto=reparto, pedido=self.pedido).exists())

        # el pedido ya asignado no debe volver a aparecer como disponible
        resp = self.client.get(reverse('repartos:reparto_form'))
        self.assertNotIn(self.pedido, list(resp.context['pedidos_disponibles']))
