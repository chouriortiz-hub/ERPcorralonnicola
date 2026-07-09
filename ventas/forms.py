from django import forms

from .models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'cuit_dni', 'condicion_iva', 'direccion', 'telefono', 'email', 'activo']
