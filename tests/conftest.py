import os

import django


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()
