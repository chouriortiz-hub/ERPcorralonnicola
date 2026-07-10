"""
Módulo STOCK
------------
Es el módulo central del ERP: expone el stock REAL de cada producto del
corralón y es el único lugar donde se modifica esa cifra (a través de
`MovimientoStock` y la función `registrar_movimiento`). Tanto COMPRAS
como VENTAS/PEDIDOS llaman a esta función en vez de tocar `stock_actual`
directamente: así el stock nunca queda "desincronizado".

Punto clave pedido por el usuario:
El campo `descuenta_stock` en Producto permite discriminar qué productos
descuentan stock automáticamente al facturarse/pedirse (ej: cemento,
ladrillos, hierro) y cuáles NO (ej: fletes, mano de obra, productos "a
pedido"/por encargo, servicios).
"""
from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.models import User


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    """Vive acá porque tanto STOCK como COMPRAS lo necesitan."""
    nombre = models.CharField(max_length=150)
    cuit = models.CharField(max_length=20, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class UnidadMedida(models.TextChoices):
    UNIDAD = 'UN', 'Unidad'
    KILOGRAMO = 'KG', 'Kilogramo'
    METRO = 'MT', 'Metro'
    METRO_CUADRADO = 'M2', 'Metro cuadrado'
    METRO_CUBICO = 'M3', 'Metro cúbico'
    LITRO = 'LT', 'Litro'
    BOLSA = 'BOL', 'Bolsa'
    PALLET = 'PAL', 'Pallet'


class Producto(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=200)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    proveedor_habitual = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos'
    )
    unidad_medida = models.CharField(max_length=3, choices=UnidadMedida.choices, default=UnidadMedida.UNIDAD)

    # --- Stock real ---
    stock_actual = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    stock_minimo = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    # --- Valorización (PMP: Precio Medio Ponderado, igual que la guía) ---
    pmp = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # --- Precios de venta ---
    precio_venta = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # --- EL FLAG PEDIDO POR EL USUARIO ---
    descuenta_stock = models.BooleanField(
        default=True,
        help_text=(
            'Si está activo, este producto descuenta stock automáticamente '
            'al confirmarse un pedido/factura. Desactivalo para productos '
            'por encargo, fletes, servicios o ítems que no se controlan en stock.'
        ),
    )

    # --- Ficha informativa (carga manual, solo Administrador) ---
    descripcion_uso = models.TextField(
        blank=True,
        verbose_name='Descripción / uso',
        help_text='Ficha visible para todos los roles. Solo el Administrador puede editarla.',
    )

    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'

    @property
    def bajo_stock_minimo(self):
        return self.descuenta_stock and self.stock_actual <= self.stock_minimo

    @property
    def valor_stock(self):
        return self.stock_actual * self.precio_venta


class MovimientoStock(models.Model):
    """
    Registro histórico e inmutable de TODO cambio de stock. Es la
    trazabilidad que exige la guía ("cada registro debe incluir un
    ForeignKey a User"), aplicada acá a cada movimiento.
    """
    ENTRADA = 'ENTRADA'
    SALIDA = 'SALIDA'
    AJUSTE = 'AJUSTE'
    TIPO_CHOICES = [
        (ENTRADA, 'Entrada (compra / ajuste positivo)'),
        (SALIDA, 'Salida (venta / ajuste negativo)'),
        (AJUSTE, 'Ajuste manual de inventario'),
    ]

    ORIGEN_COMPRA = 'COMPRA'
    ORIGEN_PEDIDO = 'PEDIDO'
    ORIGEN_AJUSTE = 'AJUSTE_MANUAL'
    ORIGEN_BOLETA = 'BOLETA'
    ORIGEN_AJUSTE_BOLETA = 'AJUSTE_BOLETA'
    ORIGEN_IMPORTACION = 'IMPORTACION_EXCEL'
    ORIGEN_CHOICES = [
        (ORIGEN_COMPRA, 'Compra a proveedor'),
        (ORIGEN_PEDIDO, 'Pedido / Venta mostrador'),
        (ORIGEN_AJUSTE, 'Ajuste manual'),
        (ORIGEN_BOLETA, 'Boleta de stock'),
        (ORIGEN_AJUSTE_BOLETA, 'Corrección retroactiva de boleta'),
        (ORIGEN_IMPORTACION, 'Importación masiva desde Excel'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    stock_resultante = models.DecimalField(max_digits=14, decimal_places=3)

    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES)
    referencia_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='ID de la Compra o el Pedido que originó este movimiento.'
    )

    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='movimientos_stock')
    motivo = models.CharField(max_length=250, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.tipo} {self.cantidad} {self.producto.codigo} ({self.origen})'


@transaction.atomic
def registrar_movimiento(producto, cantidad, tipo, origen, usuario, referencia_id=None, motivo=''):
    """
    Punto ÚNICO de entrada para modificar stock. Todo el sistema (compras,
    ventas/pedidos, ajustes manuales) pasa por acá, garantizando que el
    stock mostrado en el módulo STOCK sea siempre el real.

    - tipo ENTRADA: suma `cantidad` al stock.
    - tipo SALIDA: resta `cantidad`, validando que no quede negativo.
    - tipo AJUSTE: suma `cantidad` (puede ser negativa) sin validar mínimos.
    """
    producto = Producto.objects.select_for_update().get(pk=producto.pk)

    if tipo == MovimientoStock.SALIDA:
        if producto.stock_actual - cantidad < 0:
            raise ValidationError(
                f'Stock insuficiente para "{producto.nombre}". '
                f'Disponible: {producto.stock_actual} {producto.get_unidad_medida_display()}.'
            )
        producto.stock_actual -= cantidad
    else:
        producto.stock_actual += cantidad

    producto.save(update_fields=['stock_actual', 'actualizado'])

    return MovimientoStock.objects.create(
        producto=producto,
        tipo=tipo,
        cantidad=cantidad,
        stock_resultante=producto.stock_actual,
        origen=origen,
        referencia_id=referencia_id,
        usuario=usuario,
        motivo=motivo,
    )


def update_pmp(producto, nueva_cantidad, nuevo_precio_unitario):
    """
    Recalcula el Precio Medio Ponderado del producto al recibir una compra,
    exactamente con la lógica de la guía técnica (sección 7).
    """
    stock_previo = producto.stock_actual
    pmp_previo = producto.pmp
    total_qty = stock_previo + nueva_cantidad
    if total_qty > 0:
        nuevo_pmp = ((stock_previo * pmp_previo) + (nueva_cantidad * nuevo_precio_unitario)) / total_qty
        producto.pmp = nuevo_pmp
        producto.save(update_fields=['pmp'])
    return producto.pmp


class Boleta(models.Model):
    """
    Comprobante (remito/boleta de depósito) que agrupa una o más líneas de
    entrada o salida de stock, con un adjunto opcional (foto/PDF) sobre el
    que el navegador puede correr OCR para precargar las líneas (ver
    `stock/static/stock/boleta_ocr.js`). A diferencia de un ajuste manual
    suelto, la Boleta se corrige o anula como bloque completo (ver
    `services.ajustar_boleta` / `services.anular_boleta`): nunca se borra
    físicamente, para no perder trazabilidad de qué movimientos generó.
    """
    ENTRADA = MovimientoStock.ENTRADA
    SALIDA = MovimientoStock.SALIDA
    TIPO_CHOICES = [
        (ENTRADA, 'Entrada (recepción de mercadería)'),
        (SALIDA, 'Salida (retiro / consumo)'),
    ]

    BORRADOR = 'BORRADOR'
    CONFIRMADA = 'CONFIRMADA'
    ANULADA = 'ANULADA'
    ESTADO_CHOICES = [
        (BORRADOR, 'Borrador'),
        (CONFIRMADA, 'Confirmada'),
        (ANULADA, 'Anulada'),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    numero = models.CharField(max_length=50, unique=True)
    fecha = models.DateField()
    responsable = models.CharField(
        max_length=150, blank=True,
        help_text='Quién recibió o despachó la mercadería (texto libre, ej. nombre del chofer o cliente).',
    )
    monto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Monto total del comprobante, si corresponde (respaldo cuando no hay adjunto).',
    )
    archivo = models.FileField(upload_to='boletas/%Y/%m/', blank=True, null=True)
    ocr_texto = models.TextField(blank=True, help_text='Texto crudo detectado por OCR sobre el adjunto, guardado como respaldo.')
    observaciones = models.CharField(max_length=250, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default=BORRADOR)

    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='boletas_stock')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha', '-creado']
        verbose_name_plural = 'Boletas'

    def __str__(self):
        return f'Boleta #{self.numero} ({self.get_tipo_display()})'

    @property
    def total_items(self):
        return self.items.count()


class BoletaItem(models.Model):
    boleta = models.ForeignKey(Boleta, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='items_boleta')
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    nota = models.CharField(max_length=200, blank=True)
    texto_original = models.CharField(
        max_length=250, blank=True,
        help_text='Línea de texto tal como la detectó el OCR, para poder auditar el match automático.',
    )
    confianza = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Score de confianza (0-100) del match automático por OCR, si esta línea vino de ahí.',
    )

    def __str__(self):
        return f'{self.producto.codigo} x {self.cantidad}'


class Nota(models.Model):
    """Bitácora libre de depósito: observaciones que no encajan en un
    movimiento estructurado, pudiendo agendar productos puntuales (con su
    stock del día congelado, ver `NotaProducto`) y/o referenciar movimientos
    concretos (que ya son inmutables por diseño, ver `MovimientoStock`)."""
    titulo = models.CharField(max_length=150)
    texto = models.TextField()
    movimientos = models.ManyToManyField(MovimientoStock, blank=True, related_name='notas')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='notas_stock')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']

    def __str__(self):
        return self.titulo


class NotaProducto(models.Model):
    """
    Registro CONGELADO del stock de un producto al momento de agendarlo en
    una Nota. A propósito no es un simple M2M a Producto: si el stock real
    cambia después (o incluso si el producto cambia de nombre/código), este
    número y estos textos no se actualizan — quedan a modo de registro de
    "cuánto había ese día", no como un enlace en vivo al producto.
    """
    nota = models.ForeignKey(Nota, on_delete=models.CASCADE, related_name='producto_snapshots')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='+')
    codigo_registrado = models.CharField(max_length=30)
    nombre_registrado = models.CharField(max_length=200)
    stock_registrado = models.DecimalField(max_digits=14, decimal_places=3)
    unidad_medida_registrada = models.CharField(max_length=3, choices=UnidadMedida.choices)

    class Meta:
        verbose_name_plural = 'Snapshots de producto en notas'

    def __str__(self):
        return f'{self.codigo_registrado} = {self.stock_registrado} (al {self.nota.creado:%d/%m/%Y})'
