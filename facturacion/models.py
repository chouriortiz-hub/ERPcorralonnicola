"""
Módulo FACTURACIÓN
-------------------
Genera comprobantes electrónicos a partir de un Pedido confirmado y
gestiona la solicitud de CAE ante ARCA (ex-AFIP), el organismo de
facturación electrónica de Argentina.

Importante sobre la integración con ARCA:
La conexión real requiere, fuera de este código:
  1) Un Certificado Digital (.crt) y clave privada (.key) asociados al
     CUIT del corralón, generados desde el sitio de ARCA.
  2) Autenticación previa contra el WSAA (Web Service de Autenticación
     y Autorización) para obtener un Token + Sign temporales.
  3) El servicio de facturación WSFEv1 (o el que corresponda a tu
     categoría) para solicitar el CAE de cada comprobante.
  4) Una librería SOAP/cliente ya probada, como `pyafipws` o `zeep`.

Este módulo deja armada toda la estructura de datos y el punto de
integración (`facturacion/services.py::ARCAService`) para que un
desarrollador conecte esas credenciales de forma segura (nunca hardcodeadas,
siempre por variables de entorno).
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.models import User
from ventas.models import Cliente, Pedido


class PuntoVenta(models.Model):
    numero = models.PositiveIntegerField(unique=True)
    nombre = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f'PV {self.numero:04d} {self.nombre}'.strip()


class TipoComprobante(models.TextChoices):
    FACTURA_A = 'A', 'Factura A'
    FACTURA_B = 'B', 'Factura B'
    FACTURA_C = 'C', 'Factura C'
    NOTA_CREDITO_A = 'NCA', 'Nota de Crédito A'
    NOTA_CREDITO_B = 'NCB', 'Nota de Crédito B'


class Factura(models.Model):
    PENDIENTE = 'PENDIENTE'
    AUTORIZADA = 'AUTORIZADA'
    RECHAZADA = 'RECHAZADA'
    ANULADA = 'ANULADA'
    ESTADO_CHOICES = [
        (PENDIENTE, 'Pendiente de CAE'),
        (AUTORIZADA, 'Autorizada por ARCA'),
        (RECHAZADA, 'Rechazada por ARCA'),
        (ANULADA, 'Anulada'),
    ]

    pedido = models.OneToOneField(Pedido, on_delete=models.PROTECT, related_name='factura')
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='facturas')
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT)
    tipo_comprobante = models.CharField(max_length=3, choices=TipoComprobante.choices)
    numero = models.PositiveIntegerField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iva = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # --- Datos que devuelve ARCA al autorizar ---
    cae = models.CharField(max_length=20, blank=True, null=True)
    cae_vencimiento = models.DateField(blank=True, null=True)

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=PENDIENTE)
    motivo_rechazo = models.CharField(max_length=250, blank=True)

    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='facturas_emitidas')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.tipo_comprobante} {self.punto_venta.numero:04d}-{self.numero or "s/n"}'

    @transaction.atomic
    def generar_desde_pedido(self):
        """Copia las líneas del pedido a la factura y calcula totales."""
        if self.pk is None:
            raise ValidationError('Guardá la factura antes de generar las líneas.')
        self.lineas.all().delete()
        subtotal = 0
        for linea in self.pedido.lineas.select_related('producto'):
            FacturaLinea.objects.create(
                factura=self,
                producto=linea.producto,
                cantidad=linea.cantidad,
                precio_unitario=linea.precio_unitario,
            )
            subtotal += linea.subtotal

        self.subtotal = subtotal
        self.iva = round(subtotal * Decimal('0.21'), 2)  # ajustar según condición de IVA / tipo de comprobante
        self.total = self.subtotal + self.iva
        self.save(update_fields=['subtotal', 'iva', 'total'])

    @transaction.atomic
    def marcar_autorizada(self, cae, cae_vencimiento, numero):
        self.cae = cae
        self.cae_vencimiento = cae_vencimiento
        self.numero = numero
        self.estado = self.AUTORIZADA
        self.save(update_fields=['cae', 'cae_vencimiento', 'numero', 'estado'])

        self.pedido.estado = Pedido.FACTURADO
        self.pedido.save(update_fields=['estado'])

        # Interconexión con FINANZAS: asiento contable automático.
        from finanzas.services import post_invoice
        post_invoice(self)

    def marcar_rechazada(self, motivo):
        self.estado = self.RECHAZADA
        self.motivo_rechazo = motivo
        self.save(update_fields=['estado', 'motivo_rechazo'])


class FacturaLinea(models.Model):
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey('stock.Producto', on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario
