from importlib import import_module

utils = import_module('django-dia.utils')


def test_get_model_name(django_user_model):
    assert utils.get_model_name(django_user_model) == 'User'


# def test_get_model_
