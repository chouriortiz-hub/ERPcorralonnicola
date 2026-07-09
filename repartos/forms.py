from django import forms

from core.models import User

from .models import Reparto, Vehiculo


class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = ['patente', 'descripcion', 'activo']


class RepartoForm(forms.ModelForm):
    class Meta:
        model = Reparto
        fields = ['fecha', 'chofer', 'vehiculo', 'observaciones']
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['chofer'].queryset = User.objects.filter(activo=True).order_by('username')
        self.fields['vehiculo'].queryset = Vehiculo.objects.filter(activo=True).order_by('patente')
