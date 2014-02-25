Goals
=====

Sometimes you need generate a database diagram for your Django project.
`django-extensions`_ does this well,
but drops non-editable file such as PNG.
Even when you use SVG format you'll waste much time with bunch of objects that are not stitched together:
when you move a table, you'll need to move all connected arrows and captions.

There was a time when you could generate .dia file directly with django-extensions.
But dia support `was dropped`_.

.. _django-extensions: https://github.com/django-extensions/django-extensions
.. _was dropped: https://bugs.launchpad.net/ubuntu/+source/graphviz/+bug/745669

Using
=====

Add *django-dia* to your *INSTALLED_APPS*:

.. code:: python

    INSTALLED_APPS = (
        #...
        'djando-dia',
    )

And run

.. code:: bash

    ./manage.py make_diagram -a -e -o scheme
    ./manage.py make_diagram -e -o scheme my_app1 my_app2

This will produce file *scheme.dia* in your project directory.
