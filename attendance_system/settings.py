"""
Django settings for attendance_system project.
"""

from pathlib import Path
from datetime import timedelta
import os

# BASE DIR
BASE_DIR = Path(__file__).resolve().parent.parent


# ============================
# SECURITY
# ============================
SECRET_KEY = 'django-insecure-your-secret-key-here-change-in-production'
DEBUG = True
ALLOWED_HOSTS = ["*"]


# ============================
# INSTALLED APPS
# ============================
INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',

    # Local apps
    'detection',
    'dashboard',
    'messaging',
]


# ============================
# MIDDLEWARE
# ============================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Debe ir primero
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ============================
# URLS / WSGI
# ============================
ROOT_URLCONF = 'attendance_system.urls'
WSGI_APPLICATION = 'attendance_system.wsgi.application'


# ============================
# TEMPLATES (para React build)
# ============================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR.parent / 'SP' / 'build',  # React build/index.html
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ============================
# DATABASE
# ============================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ============================
# AUTH
# ============================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ============================
# INTERNATIONALIZATION
# ============================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ============================
# STATIC & MEDIA
# ============================
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    # BASE_DIR.parent / 'SP' / 'build' / 'static',  # Archivos del build de React
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ============================
# REST FRAMEWORK
# ============================
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # Cambiar en producción
    ],
}


# ============================
# JWT AUTH
# ============================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,

    'AUTH_HEADER_TYPES': ('Bearer',),
}


# ============================
# CORS
# ============================
CORS_ALLOW_ALL_ORIGINS = True  # Para desarrollo

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
]


# ============================
# RABBITMQ CONFIG
# ============================
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'guest'
RABBITMQ_PASSWORD = 'guest'


# ============================
# LOGGING
# ============================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'debug.log',
        },
    },

    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },

    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'detection': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}


# ============================
# CUSTOM SETTINGS
# ============================
MAX_CAMERAS = 10
DETECTION_INTERVAL = 1.0
YOLO_MODEL_PATH = 'yolov8n.pt'

LOGIN_URL = '/api/web/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/api/web/login/'

import os
from pathlib import Path

# ... configuración existente ...

# Configuración para Vite (React)
BASE_DIR = Path(__file__).resolve().parent.parent

# Archivos estáticos
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR.parent, 'SP', 'dist'),  # Vite usa 'dist'
]

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR.parent / 'SP' / 'dist',  # React build
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# CORS
CORS_ALLOW_ALL_ORIGINS = True  # Para desarrollo
# O específica:
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # Alternativo
]   