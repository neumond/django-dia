Goals
=====

Sometimes you need to generate a database diagram for your Django project.
`django-extensions`_ does this well,
but drops non-editable file like PNG.
Even when you use SVG format you'll waste much time with bunch of objects that are not stitched together:
when you move a table, you'll need to move all connected arrows and captions.

There was a time when you could generate .dia file directly with django-extensions.
But dia support `was dropped`_.

.. _django-extensions: https://github.com/django-extensions/django-extensions
.. _was dropped: https://bugs.launchpad.net/ubuntu/+source/graphviz/+bug/745669

Installation
============

.. code:: bash

    pip install django-dia

Using
=====

Add *django_dia* to your *INSTALLED_APPS*:

.. code:: python

    INSTALLED_APPS = (
        #...
        'django_dia',
    )

And run

.. code:: bash

    ./manage.py make_diagram -a -e -o scheme  # all apps in project
    ./manage.py make_diagram -e -o scheme my_app1 my_app2  # specific apps

This will produce file *scheme.dia* in your project directory.

Compatibility
=============

Django >= 1.8 supported. In long term set of supported versions will be
in parity with official django support.
