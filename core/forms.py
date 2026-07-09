from django import forms

from .models import Role, User, UserRole


class UsuarioForm(forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(), required=False, widget=forms.CheckboxSelectMultiple,
    )
    password = forms.CharField(
        widget=forms.PasswordInput, required=False,
        help_text='Dejar en blanco para no cambiar la contraseña de un usuario existente.',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'dni', 'telefono', 'activo', 'is_staff', 'is_superuser']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['roles'].initial = Role.objects.filter(usuarios__user=self.instance)

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and not cleaned.get('password'):
            self.add_error('password', 'La contraseña es obligatoria para un usuario nuevo.')
        return cleaned

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.is_active = usuario.activo
        password = self.cleaned_data.get('password')
        if password:
            usuario.set_password(password)
        if commit:
            usuario.save()
            UserRole.objects.filter(user=usuario).exclude(role__in=self.cleaned_data['roles']).delete()
            for role in self.cleaned_data['roles']:
                UserRole.objects.get_or_create(user=usuario, role=role)
        return usuario


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'stock_perm', 'ventas_perm', 'compras_perm', 'facturacion_perm', 'repartos_perm', 'finanzas_perm']
