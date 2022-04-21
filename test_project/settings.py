from distutils.version import StrictVersion

from django import get_version as django_version


DEBUG = True

INSTALLED_APPS = (
    # defaults from django 1.8
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # end
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


if StrictVersion(django_version()) < StrictVersion('1.9'):
    MIDDLEWARE_CLASSES = ()
