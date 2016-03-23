from setuptools import setup
from sys import argv


def is_register_command(a):
    for item in a:
        if item.startswith('-'):
            continue
        return item == 'register'
    return False

longdesc = None
if is_register_command(argv[1:]):
    with open('README.rst') as f:
        longdesc = f.read()


setup(
    name='django-dia',
    version='0.3',
    description='Generate .dia diagram of your django project\'s models',
    long_description=longdesc,
    url='https://github.com/neumond/django-dia',
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
    packages=['django-dia', 'django-dia.management', 'django-dia.management.commands'],
    package_data={'django-dia': ['templates/django-dia/empty.xml']},
    install_requires=['Django', 'six'],
)
