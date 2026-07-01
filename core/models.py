"""
Módulo CORE
-----------
Usuarios y sistema de permisos consolidados. Siguiendo el patrón de la guía
técnica: un usuario puede tener varios roles, y su permiso efectivo en cada
módulo es el MÁS ALTO entre todos sus roles (Consolidación de Permisos).

Este módulo es la base de la que dependen TODOS los demás (stock, ventas,
compras, facturación, repartos, finanzas), ya que cada movimiento del
sistema queda trazado al usuario que lo realizó.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Usuario del sistema (vendedor, depósito, administración, chofer, etc.)"""
    dni = models.CharField(max_length=20, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.get_full_name() or self.username


class Role(models.Model):
    """
    Rol funcional (ej: 'Vendedor Mostrador', 'Encargado de Depósito',
    'Administración', 'Chofer'). Cada rol define el nivel de acceso a
    cada módulo del ERP.
    """
    SIN_ACCESO = 0
    SOLO_VISUALIZACION = 1
    CREAR_MODIFICAR = 2
    ADMINISTRADOR = 3

    PERMISSION_CHOICES = [
        (SIN_ACCESO, 'Sin acceso'),
        (SOLO_VISUALIZACION, 'Solo visualización'),
        (CREAR_MODIFICAR, 'Crear/Modificar'),
        (ADMINISTRADOR, 'Administrador total'),
    ]

    name = models.CharField(max_length=100, unique=True)

    stock_perm = models.IntegerField(choices=PERMISSION_CHOICES, default=SIN_ACCESO)
    ventas_perm = models.IntegerField(choices=PERMISSION_CHOICES, default=SIN_ACCESO)
    compras_perm = models.IntegerField(choices=PERMISSION_CHOICES, default=SIN_ACCESO)
    facturacion_perm = models.IntegerField(choices=PERMISSION_CHOICES, default=SIN_ACCESO)
    repartos_perm = models.IntegerField(choices=PERMISSION_CHOICES, default=SIN_ACCESO)
    finanzas_perm = models.IntegerField(choices=PERMISSION_CHOICES, default=SIN_ACCESO)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='usuarios')

    class Meta:
        unique_together = ('user', 'role')

    def __str__(self):
        return f'{self.user} - {self.role}'
