from distutils.version import StrictVersion

from django import get_version as django_version


if StrictVersion(django_version()) >= StrictVersion('1.9'):
    from django.contrib.contenttypes.fields import GenericRelation
    from django.apps import apps
    get_models = apps.get_models
    get_apps = apps.app_configs.items
    get_app = apps.get_app_config
else:
    from django.db.models import get_models
    from django.db.models import get_apps
    from django.db.models import get_app
    try:
        from django.db.models.fields.generic import GenericRelation
        assert GenericRelation
    except ImportError:
        from django.contrib.contenttypes.generic import GenericRelation


def get_app_models_with_abstracts(app):
    appmodels = get_models(app)
    abstract_models = []
    for appmodel in appmodels:
        abstract_models = abstract_models + [abstract_model for abstract_model in appmodel.__bases__
                                             if hasattr(abstract_model, '_meta') and abstract_model._meta.abstract]
    abstract_models = list(set(abstract_models))  # remove duplicates
    return abstract_models + appmodels


def get_model_name(model):
    return model._meta.object_name


def get_full_model_list(apps, exclude_modules=set(), exclude_fields=set()):
    result = []
    for app in apps:
        result.extend(get_app_models_with_abstracts(app))

    result = list(set(result))
    if exclude_modules:
        result = list(filter(lambda model: model.__module__ not in exclude_modules, result))
    if exclude_fields:
        result = list(filter(lambda model: get_model_name(model) not in exclude_fields, result))

    return result


def get_model_abstract_fields(model):
    result = []
    for e in model.__bases__:
        if hasattr(e, '_meta') and e._meta.abstract:
            result.extend(e._meta.fields)
            result.extend(get_model_abstract_fields(e))
    return result


def prepare_field(field):
    return {
        'field': field,  # TODO: remove
        'name': field.name,
        'type': type(field).__name__,
        'comment': field.verbose_name,
        'primary_key': field.primary_key,
        'nullable': field.null,
        'unique': field.unique,
    }
