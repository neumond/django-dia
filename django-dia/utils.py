from django.db.models.fields.related import ForeignKey, OneToOneField, ManyToManyField
from django.contrib.contenttypes.fields import GenericRelation
from django.apps import apps


def get_apps():
    return set(apps.app_configs.values())


def get_app(app_label):
    return apps.get_app_config(app_label)


def get_target_apps(appnames, allapps=False):
    apps = get_apps() if allapps else set()
    for app_label in appnames:
        apps.add(get_app(app_label))
    return list(apps)


def is_class_a_model(m):
    return hasattr(m, '_meta')


def get_app_models_with_abstracts(app):
    appmodels = set(app.get_models())
    abstract_models = set()
    for appmodel in appmodels:
        abstract_models.update({
            abstract_model for abstract_model in appmodel.__bases__
            if is_class_a_model(abstract_model) and abstract_model._meta.abstract
        })
    return list(abstract_models | appmodels)


def get_model_name(model):
    return model._meta.object_name


def get_model_applabel(model):
    return model._meta.app_label


def get_model_label(model):
    return '{}.{}'.format(get_model_applabel(model), get_model_name(model))


def get_full_model_list(apps, exclude_models=set()):
    result = set()
    for app in apps:
        result.update(get_app_models_with_abstracts(app))
    return {m for m in result if get_model_label(m) not in exclude_models}


def get_model_local_fields(model):
    return model._meta.local_fields


def get_model_pk_field(model):
    return model._meta.pk


def get_model_field_by_name(model, fname):
    return model._meta.get_field(fname)


def is_model_abstract(model):
    return model._meta.abstract


def get_model_abstract_fields(model):
    result = []
    for e in model.__bases__:
        if is_class_a_model(e) and e._meta.abstract:
            result.extend(e._meta.fields)
            result.extend(get_model_abstract_fields(e))
    return result


def get_model_m2m_fields(model):
    return model._meta.local_many_to_many


def get_m2m_through_model(m2m_field):
    # django 2.0 and higher
    if not hasattr(m2m_field, 'rel'):
        return m2m_field.remote_field.through

    # older django
    return m2m_field.rel.through


def does_m2m_auto_create_table(m2m_field):
    through = get_m2m_through_model(m2m_field)
    if is_class_a_model(through) and through._meta.auto_created:
        return True
    return False


def get_relation_target_field(rel_field):
    # newer django
    if hasattr(rel_field, 'target_field'):
        return rel_field.target_field

    # 1.8 compat
    target_model = rel_field.related_model
    if getattr(rel_field.rel, 'field_name', None):
        return target_model._meta.get_field(rel_field.rel.field_name)
    else:
        return target_model._meta.pk


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

    # find primary key and print it first
    pk = get_model_pk_field(model)
    if pk is not None:
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


def get_relation_base(start_label, end_label, dotted=False):
    color = '000000'
    if start_label == '1' and end_label == '1':
        color = 'E2A639'  # TODO: themes
    if start_label == 'n' and end_label == 'n':
        color = '75A908'  # TODO: themes

    return {
        'start_label': start_label,
        'end_label': end_label,
        'dotted': dotted,
        'directional': start_label != end_label,
        'color': color,
    }


def prepare_relation(field, start_label, end_label, dotted=False):
    # TODO: handle lazy-relationships

    assert field.is_relation

    # TODO: exclude models
    # if get_model_name(target_model) in self.exclude_models:
    #     return

    r = get_relation_base(start_label, end_label, dotted=dotted)
    r.update({
        'start_obj': field.model,
        'end_obj': field.related_model,
        'start_field': field,
        'end_field': get_relation_target_field(field),
    })
    return r


def prepare_model_relations(model):
    result = []
    abstract_fields = get_model_abstract_fields(model)

    for field in get_model_local_fields(model):
        if field.attname.endswith('_ptr_id'):  # excluding field redundant with inheritance relation
            # write test for this
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

    for field in get_model_m2m_fields(model):
        # TODO: exclude fields
        # if self.get_field_name(field) in self.exclude_fields:
        #     continue

        if isinstance(field, ManyToManyField):
            if does_m2m_auto_create_table(field):
                result.append(prepare_relation(field, 'n', 'n'))
            # otherwise ignore this m2m
        elif isinstance(field, GenericRelation):
            result.append(prepare_relation(field, 'n', 'n', dotted=True))
        else:
            raise ValueError('Wrong m2m relation field class: {}'.format(field))

    return [rel for rel in result if rel is not None]


def prepare_model_inheritance(model):
    result = []
    for parent in model.__bases__:
        if is_class_a_model(parent):
            label = 'multi-table'
            if parent._meta.abstract:
                label = 'abstract'
            if model._meta.proxy:
                label = 'proxy'
            result.append({
                'start_label': '',
                'end_label': label,
                'start_obj': model,
                'end_obj': parent,
                'dotted': True,
                'directional': True,
                'color': '000000',
            })
    return result


__all__ = (
    get_full_model_list,
    get_target_apps,
    get_model_label,
    get_model_applabel,
    get_model_name,
    prepare_model_fields,
    prepare_model_relations,
    prepare_model_inheritance,
)
