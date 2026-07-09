from django import forms

from .models import Categoria, Producto, Proveedor


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
            'stock_minimo', 'precio_venta', 'descuenta_stock', 'activo',
        ]


class AjusteStockForm(forms.Form):
    producto = forms.ModelChoiceField(queryset=Producto.objects.filter(activo=True))
    cantidad = forms.DecimalField(
        max_digits=14, decimal_places=3,
        help_text='Positiva para sumar stock, negativa para restar.',
    )
    motivo = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=True)
