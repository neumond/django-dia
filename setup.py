from setuptools import setup
from sys import argv


def is_register_command(a):
    for item in a:
        if item.startswith('-'):
            continue
        return item in ('register', 'bdist_wheel')
    return False


longdesc = None
if is_register_command(argv[1:]):
    with open('README.rst') as f:
        longdesc = f.read()


setup(
    name='django-dia',
    version='0.4.9',
    description='Generate .dia diagram of your django project\'s models',
    long_description=longdesc,
    url='https://github.com/neumond/django_dia',
    author='Vitalik Verhovodov',
    author_email='knifeslaughter@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    keywords='django dia model diagram',
    packages=['django_dia', 'django_dia.management', 'django_dia.management.commands'],
    package_data={'django_dia': ['empty.xml']},
    install_requires=['Django', 'six'],
    extras_require={
        'tests': ['pytest', 'pytest-django', 'pytest-pythonpath']
    }
)
