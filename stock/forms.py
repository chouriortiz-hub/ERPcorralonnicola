from django import forms

from .models import Boleta, Categoria, Nota, Producto, Proveedor


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre']


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'cuit', 'telefono', 'email', 'direccion', 'activo']


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'codigo', 'nombre', 'categoria', 'proveedor_habitual', 'unidad_medida',
            'stock_minimo', 'precio_venta', 'descuenta_stock', 'activo', 'descripcion_uso',
        ]
        widgets = {'descripcion_uso': forms.Textarea(attrs={'rows': 3})}


class AjusteStockForm(forms.Form):
    producto = forms.ModelChoiceField(queryset=Producto.objects.filter(activo=True))
    cantidad = forms.DecimalField(
        max_digits=14, decimal_places=3,
        help_text='Positiva para sumar stock, negativa para restar.',
    )
    motivo = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=True)


class BoletaForm(forms.ModelForm):
    """
    Cabecera de la Boleta. Las líneas (productos + cantidades) viajan aparte
    como JSON en un campo oculto del template (mismo patrón que el carrito
    de `ventas/nuevo_pedido.html`) y se resuelven en
    `services.parsear_items_boleta`. La unicidad de `numero` la valida sola
    esta ModelForm por venir del `unique=True` del modelo.
    """
    fecha = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = Boleta
        fields = ['tipo', 'numero', 'fecha', 'responsable', 'monto', 'archivo', 'observaciones']


class NotaForm(forms.ModelForm):
    """
    Solo el texto libre de la nota. Los productos a agendar (con su stock
    del día congelado) y los movimientos puntuales a referenciar viajan
    aparte como JSON en campos ocultos del template (mismo patrón "buscar y
    agregar" que el carrito de boletas) y se resuelven en
    `services.crear_nota`.
    """
    class Meta:
        model = Nota
        fields = ['titulo', 'texto']
        widgets = {'texto': forms.Textarea(attrs={'rows': 3})}


class ImportarExcelForm(forms.Form):
    archivo = forms.FileField(
        label='Planilla Excel (.xlsx)',
        help_text='Debe tener una columna "Código" y una columna "Stock" en alguna de las primeras 10 filas.',
    )
