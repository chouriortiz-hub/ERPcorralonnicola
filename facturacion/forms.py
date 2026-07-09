from django import forms

from .models import PuntoVenta


class PuntoVentaForm(forms.ModelForm):
    class Meta:
        model = PuntoVenta
        fields = ['numero', 'nombre']
