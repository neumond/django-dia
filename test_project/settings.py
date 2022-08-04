DEBUG = True

INSTALLED_APPS = (
    'django.contrib.contenttypes',
    'django_dia',
    'test_project.anyapp',
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'testdb',
    }
}

SECRET_KEY = 'mblqnc+y=9^c$44!!r9b!fw$a95@p_m31o7r3+9w4h&@tu)wps'

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
USE_TZ = True
