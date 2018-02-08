from distutils.version import StrictVersion

import six
from django import get_version as django_version
from django.db.models.fields.related import ForeignKey, OneToOneField, ManyToManyField


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
    if exclude_fields:  # TODO: fields?
        result = list(filter(lambda model: get_model_name(model) not in exclude_fields, result))

    return result


def get_model_local_fields(model):
    return model._meta.local_fields


def get_model_pk_field(model):
    return model._meta.pk


def get_model_field_by_name(model, fname):
    for field in get_model_local_fields(model):
        if field.name == fname:
            return field
    raise KeyError('Model {} has no field named {}'.format(model, fname))


def is_model_abstract(model):
    return model._meta.abstract


def get_model_abstract_fields(model):
    result = []
    for e in model.__bases__:
        if hasattr(e, '_meta') and e._meta.abstract:
            result.extend(e._meta.fields)
            result.extend(get_model_abstract_fields(e))
    return result


def get_model_m2m_relations(model):
    return model._meta.local_many_to_many


def get_model_m2m_by_name(model, fname):
    for m2m in get_model_m2m_relations(model):
        if m2m.name == fname:
            return m2m
    raise KeyError('Model {} has no m2m relation named {}'.format(model, fname))


def does_m2m_auto_create_table(m2m):
    if getattr(m2m, 'creates_table', False):  # django 1.1, TODO: remove?
        return True
    through = m2m.rel.through
    if hasattr(through, '_meta') and through._meta.auto_created:  # django 1.2
        return True
    return False


def get_related_field(field):
    return field.rel


def get_field_name(field, verbose=False):
    # TODO: need this function?
    return field.verbose_name if verbose and field.verbose_name else field.name


def prepare_field_old(field):
    # TODO: remove
    return {
        'field': field,  # TODO: remove
        'name': field.name,
        'type': type(field).__name__,
        'comment': field.verbose_name,  # TODO: comment?
        'primary_key': field.primary_key,
        'nullable': field.null,
        'unique': field.unique,
    }


def prepare_field(field):
    return {
        'name': field.name,
        'type': type(field).__name__,
        'comment': field.verbose_name,  # TODO: comment?
        'primary_key': field.primary_key,
        'nullable': field.null,
        'unique': field.unique,
    }


def prepare_model_fields(model):
    result = []

    # find primary key and print it first, ignoring implicit id if other pk exists
    pk = get_model_pk_field(model)
    if pk is not None:
        assert not is_model_abstract(model)
        result.append(prepare_field(pk))

    for field in get_model_local_fields(model):
        # TODO: exclude fields
        if field == pk:
            continue
        result.append(prepare_field(field))

    # TODO:
    # if self.sort_fields:
    #     result = sorted(result, key=lambda field: (not field['primary_key'], field['name']))

    return result


def prepare_relation(field, start_label, end_label, dotted=False):
    # handle self-relationships and lazy-relationships
    rel = get_related_field(field)

    if isinstance(rel.to, six.string_types):
        if rel.to == 'self':
            target_model = field.model
        elif rel.to == 'auth.User':  # TODO: need this?
            from django.contrib.auth import get_user_model
            target_model = get_user_model()
        elif rel.to == 'sites.Site':  # TODO: need this?
            from django.contrib.sites.models import Site
            target_model = Site
        else:
            raise Exception('Lazy relationship for model ({}) must be explicit for field ({})'
                            .format(field.model.__name__, field.name))
    else:
        target_model = rel.to

    if getattr(rel, 'field_name', None):
        target_field = target_model._meta.get_field(rel.field_name)
    else:
        target_field = target_model._meta.pk

    # TODO: exclude models
    # if get_model_name(target_model) in self.exclude_models:
    #     return

    color = '000000'
    if start_label == '1' and end_label == '1':
        color = 'E2A639'  # TODO: themes
    if start_label == 'n' and end_label == 'n':
        color = '75A908'  # TODO: themes

    return {
        'start_label': start_label,
        'end_label': end_label,
        'start_obj': field.model,
        'end_obj': target_model,
        'start_field': field,
        'end_field': target_field,
        'dotted': dotted,
        'directional': start_label != end_label,
        'color': color,
    }


def prepare_model_relations(model):
    result = []
    abstract_fields = get_model_abstract_fields(model)

    for field in get_model_local_fields(model):
        if field.attname.endswith('_ptr_id'):  # excluding field redundant with inheritance relation
            # TODO: recheck this
            continue
        if field in abstract_fields:
            # excluding fields inherited from abstract classes. they duplicate as local_fields
            continue

        # TODO: exclude fields
        # if self.get_field_name(field) in self.exclude_fields:
        #     continue

        if isinstance(field, OneToOneField):
            result.append(prepare_relation(field, '1', '1'))
        elif isinstance(field, ForeignKey):
            result.append(prepare_relation(field, 'n', '1'))
        # otherwise it's an usual field, skipping it

    for field in get_model_m2m_relations(model):
        # TODO: exclude fields
        # if self.get_field_name(field) in self.exclude_fields:
        #     continue

        if isinstance(field, ManyToManyField):
            if does_m2m_auto_create_table(field):
                result.append(prepare_relation(field, 'n', 'n'))
            else:
                pass   # TODO
        elif isinstance(field, GenericRelation):
            result.append(prepare_relation(field, 'n', 'n', dotted=True))
        else:
            raise ValueError('Wrong m2m relation field class: {}'.format(field))

    return [rel for rel in result if rel is not None]
