# ERP Corralón Nicola

Sistema de gestión a medida construido con **Python + Django**, siguiendo
la arquitectura de la guía técnica de referencia (usuarios con permisos
consolidados, transacciones atómicas, PMP automático, asientos contables
automáticos), adaptado al circuito real de un corralón:

**Stock ⇄ Compras ⇄ Ventas (Mostrador) ⇄ Facturación (ARCA) ⇄ Repartos ⇄ Finanzas**

Todos los módulos están interconectados: nada se actualiza "a mano" en
dos lugares distintos, siempre hay una única función responsable de cada
dato crítico (ver diagrama de flujo más abajo).

## 1. Instalación

```bash
python -m venv venv
source venv/bin/activate          # En Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py datos_iniciales  # Roles, categorías y punto de venta base
python manage.py createsuperuser  # Tu usuario administrador
python manage.py runserver
```

Entrá a `http://127.0.0.1:8000/` (redirige al panel de gestión).

> Nota: el panel de administración de Django (`/admin/`) es la interfaz
> operativa incluida: los vendedores de mostrador, el encargado de
> depósito y el chofer pueden trabajar directamente ahí una vez que les
> creás su usuario y les asignás un Rol. Si más adelante querés una
> interfaz de mostrador más simple (pantalla táctil, botones grandes),
> se puede construir sobre las mismas funciones de negocio ya armadas
> (`Pedido.confirmar()`, `facturar_pedido()`, etc.) sin tocar el modelo
> de datos.

## 2. Módulos

| Módulo | Qué hace | Se conecta con |
|---|---|---|
| **core** | Usuarios y permisos consolidados (un usuario con varios roles toma el permiso más alto entre todos) | Todos |
| **stock** | Stock real por producto, categorías, proveedores. Función única `registrar_movimiento()` para cualquier entrada/salida. Flag `descuenta_stock` por producto | compras, ventas, repartos |
| **compras** | Carga de compras a proveedores. Al confirmarse: actualiza PMP y genera entrada de stock | stock, finanzas |
| **ventas** | Presupuestos y Pedidos de mostrador. Al confirmar un pedido, descuenta stock **solo** de los productos con `descuenta_stock=True` | stock, facturacion, repartos |
| **facturacion** | Genera comprobantes y gestiona el CAE contra **ARCA** (ex-AFIP) | ventas, finanzas |
| **repartos** | Organiza qué pedidos salen de reparto cada día, con qué chofer y vehículo, y su estado de entrega | ventas |
| **finanzas** | Libro Diario con asientos automáticos al confirmar una compra o autorizar una factura | compras, facturacion |

## 3. El flujo de negocio de punta a punta

1. **Compra** a un proveedor → se confirma → sube el stock del producto y se
   recalcula el **PMP** (Precio Medio Ponderado) automáticamente.
2. Un vendedor arma un **Presupuesto** para un cliente (no toca stock).
3. El presupuesto se convierte en **Pedido** (o se carga un pedido directo).
4. Al **confirmar el Pedido**, el sistema recorre cada línea:
   - Si el producto tiene `descuenta_stock = True` (ej: cemento, hierro,
     ladrillos) → se descuenta del stock real y queda registrado el
     movimiento.
   - Si tiene `descuenta_stock = False` (ej: flete, mano de obra,
     productos "a pedido"/por encargue) → **no** toca stock, pero sigue
     formando parte del pedido y se factura igual.
5. El vendedor **factura** el pedido: se genera la Factura, se solicita el
   **CAE a ARCA** y, al autorizarse, el pedido pasa a estado *Facturado*.
6. Automáticamente se generan los **asientos contables** en el Libro
   Diario (finanzas).
7. Si el pedido es "Reparto a domicilio", se asigna a un **Reparto** del
   día con chofer y vehículo. Al entregarse, el pedido pasa a *Entregado*.

Este flujo completo fue probado de punta a punta (compra → stock/PMP →
pedido con descuento condicional → factura con CAE simulado → asientos
contables → reparto → entrega) y funciona correctamente.

## 4. El campo que discrimina el descuento de stock

Pediste específicamente poder elegir qué productos descuentan stock
automáticamente y cuáles no. Eso vive en:

```python
# stock/models.py -> Producto
descuenta_stock = models.BooleanField(default=True)
```

Se edita por producto desde el panel (incluso editable en la grilla de
listado, sin entrar a cada producto). Usalo en `False` para: fletes,
mano de obra, productos por encargue/a pedido especial, servicios, etc.

## 5. Conexión con ARCA (ex-AFIP) — facturación electrónica

La lógica de facturación está lista y probada, pero conectarla a ARCA
de verdad requiere datos que **solo vos podés obtener y cargar de forma
segura** (nunca deben ir en el código fuente):

1. Tramitar en ARCA el **Certificado Digital** (.crt) y su clave privada
   (.key) asociados al CUIT del corralón.
2. Elegir una librería cliente para los webservices SOAP de ARCA. Las
   más usadas en Python son `pyafipws` o construir el cliente con `zeep`
   contra WSAA (autenticación) + WSFEv1 (facturación).
3. Cargar las credenciales **solo por variables de entorno**, nunca
   hardcodeadas:

   ```bash
   export ARCA_CUIT=20XXXXXXXXX
   export ARCA_CERT_PATH=/ruta/segura/corralon.crt
   export ARCA_KEY_PATH=/ruta/segura/corralon.key
   export ARCA_PRODUCCION=False   # True cuando esté probado en homologación
   ```

4. Completar los dos métodos marcados como `NotImplementedError` en
   `facturacion/services.py::ARCAService`:
   - `_obtener_token_sign()`: login contra WSAA (el token dura ~12hs, conviene cachearlo).
   - `_solicitar_cae_real()`: arma y envía el comprobante a WSFEv1, y devuelve el CAE.

Mientras esas variables de entorno no estén configuradas, el sistema
corre en **modo simulado**: genera un CAE ficticio para que puedas
probar y usar todo el resto del circuito (stock, ventas, repartos,
finanzas) sin depender de ARCA. Esto es intencional, para que el ERP sea
utilizable desde el día uno mientras se gestiona el certificado.

## 6. Estructura del proyecto

```
corralon_nicola/     # settings, urls, wsgi/asgi
core/                 # usuarios y permisos
stock/                # productos, categorías, movimientos de stock
compras/              # compras a proveedores
ventas/                # clientes, presupuestos, pedidos
facturacion/          # comprobantes + integración ARCA
repartos/              # organización de entregas
finanzas/              # libro diario / asientos automáticos
```

## 7. Próximos pasos sugeridos

- Conectar las credenciales reales de ARCA (sección 5).
- Si querés una pantalla de mostrador más simple que el admin de Django
  (ideal para tablet/PC táctil), se puede construir con las mismas
  funciones de negocio ya armadas.
- Cargar el stock inicial real del corralón (por planilla, vía el
  admin o un importador CSV — el mismo patrón de carga masiva con
  manejo de codificación UTF-8/Latin-1 que se explica en la guía
  técnica original se puede reutilizar acá).

## 8. Desplegar en la web (multi-dispositivo, datos compartidos)

El proyecto ya viene configurado para producción: se conecta solo a
**PostgreSQL** cuando existe la variable `DATABASE_URL`, sirve los
estáticos con **Whitenoise**, corre con **Gunicorn**, y activa HTTPS/
cookies seguras automáticamente cuando `DJANGO_DEBUG=False`. Incluye
`Procfile`, `railway.toml` y `render.yaml` para que el despliegue sea
prácticamente automático.

### Paso a paso con Railway

1. Subí este proyecto a un repositorio de GitHub (puede ser privado).
2. Entrá a [railway.app](https://railway.app) y creá una cuenta.
3. "New Project" → "Deploy from GitHub repo" → elegí tu repositorio.
4. En el mismo proyecto de Railway: "New" → "Database" → "PostgreSQL".
   Railway conecta automáticamente la variable `DATABASE_URL` a tu
   servicio web, no hay que copiarla a mano.
5. En el servicio web → pestaña "Variables", agregá:
   - `DJANGO_SECRET_KEY` (generá una clave larga y random)
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS` (Railway te da un dominio tipo
     `tuapp.up.railway.app`; también podés dejarlo vacío al principio,
     el proyecto ya detecta `RAILWAY_PUBLIC_DOMAIN` solo)
6. Railway detecta `railway.toml` y hace el deploy: instala
   dependencias, corre `migrate`, `collectstatic`, y levanta Gunicorn.
7. Una vez desplegado, abrí la consola del servicio (o conectate por
   `railway run`) y ejecutá una sola vez:
   ```
   python manage.py datos_iniciales
   python manage.py createsuperuser
   ```
8. Entrá a la URL pública que te da Railway. Ya está disponible desde
   cualquier dispositivo, todos comparten la misma base de datos.

### Paso a paso con Render (alternativa)

1. Subí el proyecto a GitHub.
2. En [render.com](https://render.com), creá una cuenta y elegí
   "New" → "Blueprint", apuntando a tu repo (usa el `render.yaml`
   incluido, que ya define el servicio web + la base Postgres).
3. Render crea automáticamente la base de datos y conecta
   `DATABASE_URL` sola.
4. Una vez desplegado, desde la consola/shell del servicio, corré una
   sola vez:
   ```
   python manage.py datos_iniciales
   python manage.py createsuperuser
   ```
5. Entrá a la URL pública (`https://erp-corralon-nicola.onrender.com`).

### Dominio propio (opcional)

En ambos servicios podés agregar un dominio propio
(`erp.corralonnicola.com.ar`) desde la sección "Settings" → "Domains",
apuntando un registro CNAME desde donde compraste el dominio. Después
sumá ese dominio a `DJANGO_ALLOWED_HOSTS`.

### Qué NO cambia con este despliegue

Ningún módulo, modelo, ni función de negocio se modificó para esto.
El flujo compra → stock → pedido → factura → reparto → finanzas
funciona exactamente igual; simplemente ahora corre en un servidor
compartido en vez de en tu máquina.

