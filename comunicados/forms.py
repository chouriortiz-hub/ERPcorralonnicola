from django import forms

from .models import Aviso


class AvisoForm(forms.ModelForm):
    fecha_vencimiento = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
    )

    class Meta:
        model = Aviso
        fields = ['titulo', 'mensaje', 'tipo', 'productos', 'fecha_vencimiento', 'activo']
        widgets = {
            'productos': forms.SelectMultiple(attrs={'size': 8}),
        }
