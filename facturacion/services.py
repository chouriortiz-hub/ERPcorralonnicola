"""
ARCAService
-----------
Capa de integración con ARCA (Agencia de Recaudación y Control Aduanero,
ex-AFIP), el organismo que autoriza la facturación electrónica en
Argentina mediante la asignación de un CAE (Código de Autorización
Electrónico) a cada comprobante.

Este archivo define el CONTRATO/interfaz que usa el resto del ERP
(`Factura.marcar_autorizada`, vistas de facturación, etc.) para pedir un
CAE, sin acoplar el resto del sistema a los detalles del webservice SOAP.

Para dejarlo productivo, un desarrollador debe:
  1) Tramitar en ARCA el Certificado Digital (.crt/.key) del corralón.
  2) Instalar una librería cliente probada, por ejemplo:
         pip install pyafipws
     o construir el cliente sobre WSAA/WSFEv1 con `zeep` (SOAP).
  3) Completar las credenciales SOLO por variables de entorno (nunca en
     el código ni en el repositorio):
         ARCA_CUIT, ARCA_CERT_PATH, ARCA_KEY_PATH, ARCA_PRODUCCION
     (ver corralon_nicola/settings.py, sección ARCA).
  4) Implementar `_obtener_token_sign()` (llamada a WSAA, se cachea
     ~12hs) y `_solicitar_cae_real()` (llamada a WSFEv1 pasándole los
     datos del comprobante: tipo, punto de venta, importe, CUIT del
     cliente, etc.) reemplazando el modo `simulado` de abajo.

Mientras esas credenciales no estén configuradas, el servicio corre en
modo SIMULADO: genera un CAE ficticio para que todo el circuito interno
del ERP (pedido -> factura -> stock -> finanzas) se pueda probar de
punta a punta sin depender de ARCA.
"""
import random
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


class ARCAIntegrationError(Exception):
    """Se lanza cuando ARCA rechaza el comprobante o falla la conexión."""


class ARCAService:
    def __init__(self):
        self.cuit = getattr(settings, 'ARCA_CUIT', None)
        self.cert_path = getattr(settings, 'ARCA_CERT_PATH', None)
        self.key_path = getattr(settings, 'ARCA_KEY_PATH', None)
        self.produccion = getattr(settings, 'ARCA_PRODUCCION', False)
        self.modo_simulado = not (self.cuit and self.cert_path and self.key_path)

    def solicitar_cae(self, factura):
        """
        Punto de entrada usado por el ERP. Devuelve un dict:
            {'numero': int, 'cae': str, 'cae_vencimiento': date}
        o levanta ARCAIntegrationError si ARCA rechaza el comprobante.
        """
        if self.modo_simulado:
            return self._solicitar_cae_simulado(factura)
        return self._solicitar_cae_real(factura)

    # ------------------------------------------------------------------
    # MODO SIMULADO (para desarrollo/pruebas mientras no hay certificado)
    # ------------------------------------------------------------------
    def _solicitar_cae_simulado(self, factura):
        from facturacion.models import Factura
        ultimo = (
            Factura.objects.filter(punto_venta=factura.punto_venta, tipo_comprobante=factura.tipo_comprobante)
            .exclude(numero=None)
            .order_by('-numero')
            .first()
        )
        siguiente_numero = (ultimo.numero + 1) if ultimo else 1
        return {
            'numero': siguiente_numero,
            'cae': str(random.randint(10**13, 10**14 - 1)),
            'cae_vencimiento': timezone.now().date() + timedelta(days=10),
        }

    # ------------------------------------------------------------------
    # MODO REAL — completar con pyafipws / zeep + certificado del corralón
    # ------------------------------------------------------------------
    def _obtener_token_sign(self):
        raise NotImplementedError(
            'Configurar autenticación WSAA con el certificado de ARCA '
            '(ver docstring de este archivo).'
        )

    def _solicitar_cae_real(self, factura):
        raise NotImplementedError(
            'Conectar acá el webservice WSFEv1 de ARCA usando '
            'self._obtener_token_sign() y los datos de `factura`.'
        )
