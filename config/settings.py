import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Add apps folder to Python path
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-for-development-only-ryuclass')
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    
    # Custom local apps
    'users.apps.UsersConfig',
    'courses.apps.CoursesConfig',
    'payments.apps.PaymentsConfig',
    'quizzes.apps.QuizzesConfig',
    'affiliates.apps.AffiliatesConfig',
    'support.apps.SupportConfig',
    'system_config.apps.SystemConfigConfig',
    'community.apps.CommunityConfig',
]

UNFOLD = {
    "SITE_TITLE": "RyuClass Admin",
    "SITE_HEADER": "RyuClass Admin Portal",
    "SITE_URL": "/",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "แดชบอร์ดหลัก",
                "separator": True,
                "items": [
                    {
                        "title": "หน้าแรกแดชบอร์ด",
                        "icon": "dashboard",
                        "link": "/admin/",
                    },
                ],
            },
            {
                "title": "การเงิน",
                "separator": True,
                "items": [
                    {
                        "title": "แจ้งชำระเงิน / สลิป",
                        "icon": "payments",
                        "link": "/admin/payments/payment/",
                    },
                    {
                        "title": "ระบบแนะนำ (Affiliates)",
                        "icon": "group",
                        "link": "/admin/affiliates/affiliateprofile/",
                    },
                ],
            },
            {
                "title": "คอร์สเรียน",
                "separator": True,
                "items": [
                    {
                        "title": "คอร์สเรียน",
                        "icon": "school",
                        "link": "/admin/courses/course/",
                    },
                    {
                        "title": "โมดูลบทเรียน",
                        "icon": "view_module",
                        "link": "/admin/courses/module/",
                    },
                    {
                        "title": "คลิปบทเรียน",
                        "icon": "play_circle",
                        "link": "/admin/courses/lesson/",
                    },
                    {
                        "title": "สิทธิ์การเข้าเรียน",
                        "icon": "assignment_ind",
                        "link": "/admin/courses/enrollment/",
                    },
                ],
            },
            {
                "title": "ผู้ใช้งาน & สนับสนุน",
                "separator": True,
                "items": [
                    {
                        "title": "ผู้ใช้งานทั้งหมด",
                        "icon": "person",
                        "link": "/admin/users/user/",
                    },
                    {
                        "title": "ตั๋วขอความช่วยเหลือ",
                        "icon": "confirmation_number",
                        "link": "/admin/support/supportticket/",
                    },
                ],
            },
        ],
    },
}


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be at the top
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'u450627396_ryuclass'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASS', ''),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES', FOREIGN_KEY_CHECKS=0",
        }
    }
}

# Password validation
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

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Internationalization
LANGUAGE_CODE = 'th'
TIME_ZONE = 'Asia/Bangkok'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

admin_lte_path = BASE_DIR.parent / 'AdminLTE-3.1.0'
if admin_lte_path.exists():
    STATICFILES_DIRS.append(admin_lte_path)

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


# CORS Config
_cors_origins = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'https://www.ryusosense.online,https://ryusosense.online,https://ryuclassv2.vercel.app,http://localhost:3000,http://127.0.0.1:3000',
)
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins.split(',') if origin.strip()]
CORS_ALLOW_CREDENTIALS = True

# Reverse Proxy & SSL Settings for Nginx / Cloudflare
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

_csrf_origins = os.getenv(
    'CSRF_TRUSTED_ORIGINS',
    'https://ryuapp-tanchon.tanchonhomeserverxxx.online,https://www.ryusosense.online,https://ryusosense.online',
)
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_origins.split(',') if origin.strip()]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ── Email Settings (Hostinger SMTP / Custom SMTP) ───
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.hostinger.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 465))
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'True') == 'True'
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
