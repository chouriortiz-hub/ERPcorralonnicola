from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Role, User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [UserRoleInline]
    list_display = ('username', 'first_name', 'last_name', 'email', 'activo', 'is_staff')
    list_filter = DjangoUserAdmin.list_filter + ('activo',)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'stock_perm', 'ventas_perm', 'compras_perm',
        'facturacion_perm', 'repartos_perm', 'finanzas_perm',
    )
