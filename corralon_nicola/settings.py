"""
Django settings for corralon_nicola project.

ERP a medida para Corralón Nicola: stock, ventas (mostrador), compras,
facturación electrónica (ARCA) y repartos.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: en producción, definir SECRET_KEY y DEBUG por variable
# de entorno y NUNCA commitear el valor real al repositorio.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-4!pj9grhigtqp&swt3zki)51)hs%*%!ro3(q1jro^^r1_4utz=',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

# Railway/Render exponen el dominio público en esta variable; si existe,
# se agrega automáticamente a ALLOWED_HOSTS sin que tengas que tocar nada.
RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
if RAILWAY_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_DOMAIN)
RENDER_DOMAIN = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_DOMAIN:
    ALLOWED_HOSTS.append(RENDER_DOMAIN)

CSRF_TRUSTED_ORIGINS = [f'https://{h}' for h in ALLOWED_HOSTS if h not in ('localhost', '127.0.0.1')]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps propias del ERP
    'core',
    'stock',
    'compras',
    'ventas',
    'facturacion',
    'repartos',
    'finanzas',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'corralon_nicola.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.permisos',
            ],
        },
    },
]

WSGI_APPLICATION = 'corralon_nicola.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases
#
# - En tu máquina local (sin DATABASE_URL definida): usa SQLite, como hasta ahora.
# - En producción (Railway/Render te dan DATABASE_URL automáticamente al crear
#   la base Postgres del proyecto): se conecta sola a Postgres, sin tocar código.

import dj_database_url

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'es-ar'

TIME_ZONE = 'America/Argentina/Buenos_Aires'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Modelo de usuario propio (core.User)
AUTH_USER_MODEL = 'core.User'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'


# ---------------------------------------------------------------------------
# ARCA (ex-AFIP) — Facturación electrónica Argentina
# Completar SOLO por variables de entorno, nunca hardcodear en el código.
# Ver facturacion/services.py::ARCAService para el detalle de integración.
# ---------------------------------------------------------------------------
ARCA_CUIT = os.environ.get('ARCA_CUIT')                # CUIT del corralón
ARCA_CERT_PATH = os.environ.get('ARCA_CERT_PATH')      # ruta al certificado .crt
ARCA_KEY_PATH = os.environ.get('ARCA_KEY_PATH')        # ruta a la clave privada .key
ARCA_PRODUCCION = os.environ.get('ARCA_PRODUCCION', 'False') == 'True'

BASE_CURRENCY = 'ARS'


# ---------------------------------------------------------------------------
# Seguridad en producción (se activa sola cuando DEBUG=False)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7  # 1 semana, se puede subir con el tiempo
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
