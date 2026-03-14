from stock_control.settings import *
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'services/data_storage/db.sqlite3',
    }
}
