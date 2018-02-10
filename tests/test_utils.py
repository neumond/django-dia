from importlib import import_module

import pytest

from test_project.anyapp import models as anyapp_models
utils = import_module('django-dia.utils')


@pytest.fixture
def anyapp():
    return utils.get_app('anyapp')


def test_get_model_name(django_user_model):
    assert utils.get_model_name(django_user_model) == 'User'
    assert utils.get_model_name(anyapp_models.Person) == 'Person'


def test_get_target_apps():
    f = utils.get_target_apps

    assert len(f(())) == 0
    assert len(f((), allapps=True)) > 0
    assert len(f(('anyapp', ))) == 1


def test_get_app_models_with_abstracts(anyapp):
    # usual django mechanism
    models = set(anyapp.get_models())
    assert anyapp_models.Circle in models
    assert anyapp_models.AbstractShape not in models

    modelswa = utils.get_app_models_with_abstracts(anyapp)
    assert len(modelswa) > len(models)
    assert anyapp_models.Circle in modelswa
    assert anyapp_models.AbstractShape in modelswa


def test_get_model_abstract_fields():
    f = utils.get_model_abstract_fields
    assert len(f(anyapp_models.Person)) == 0
    assert len(f(anyapp_models.Square)) == 1
    assert len(f(anyapp_models.Circle)) == 1


def test_get_model_local_fields():
    f = utils.get_model_local_fields
    assert len(f(anyapp_models.Person)) == 3  # includes pk

    # inherited models contain all abstract fields and pk
    assert len(f(anyapp_models.Square)) == 3
    assert len(f(anyapp_models.Circle)) == 3

    # while abstract models contain only their explicitly defined fields
    assert len(f(anyapp_models.AbstractShape)) == 1


def test_get_model_pk_field():
    f = utils.get_model_pk_field
    assert f(anyapp_models.Person) is not None
    assert f(anyapp_models.Square) is not None
    assert f(anyapp_models.AbstractShape) is None


class AnyValue:
    def __eq__(self, other):
        return True


def test_prepare_model_fields_Person():
    data = utils.prepare_model_fields(anyapp_models.Person)
    assert data == [
        {
            'name': 'id',
            'type': 'AutoField',
            'comment': AnyValue(),
            'primary_key': True,
            'nullable': False,
            'unique': True,
        },
        {
            'name': 'first_name',
            'type': 'CharField',
            'comment': 'First name of a person',
            'primary_key': False,
            'nullable': False,
            'unique': False,
        },
        {
            'name': 'last_name',
            'type': 'CharField',
            'comment': AnyValue(),
            'primary_key': False,
            'nullable': False,
            'unique': False,
        },
    ]


def test_prepare_model_fields_AbstractShape():
    data = utils.prepare_model_fields(anyapp_models.AbstractShape)
    assert data == [
        # No ID field here
        {
            'name': 'area',
            'type': 'FloatField',
            'comment': AnyValue(),
            'primary_key': False,
            'nullable': False,
            'unique': False,
        },
    ]


def test_relations_1_n():
    data = utils.prepare_model_relations(anyapp_models.Comment)
    assert data == [
        {
            'start_label': 'n',
            'end_label': '1',
            'start_obj': anyapp_models.Comment,
            'end_obj': anyapp_models.Post,
            'start_field': utils.get_model_field_by_name(anyapp_models.Comment, 'post'),
            'end_field': utils.get_model_pk_field(anyapp_models.Post),
            'color': AnyValue(),
            'dotted': False,
            'directional': True,
        }
    ]

    data = utils.prepare_model_relations(anyapp_models.Post)
    assert data == []  # no arrow duplicates from another side


def test_relations_1_1():
    data = utils.prepare_model_relations(anyapp_models.Engine)
    assert data == [
        {
            'start_label': '1',
            'end_label': '1',
            'start_obj': anyapp_models.Engine,
            'end_obj': anyapp_models.Automobile,
            'start_field': utils.get_model_field_by_name(anyapp_models.Engine, 'automobile'),
            'end_field': utils.get_model_pk_field(anyapp_models.Automobile),
            'color': AnyValue(),
            'dotted': False,
            'directional': False,
        }
    ]

    data = utils.prepare_model_relations(anyapp_models.Automobile)
    assert data == []  # no arrow duplicates from another side


def test_relations_n_n():
    assert len(utils.get_model_m2m_fields(anyapp_models.Speaker)) == 1
    assert len(utils.get_model_m2m_fields(anyapp_models.Language)) == 0

    data = utils.prepare_model_relations(anyapp_models.Speaker)
    assert data == [
        {
            'start_label': 'n',
            'end_label': 'n',
            'start_obj': anyapp_models.Speaker,
            'end_obj': anyapp_models.Language,
            'start_field': utils.get_model_field_by_name(anyapp_models.Speaker, 'language'),
            'end_field': utils.get_model_pk_field(anyapp_models.Language),
            'color': AnyValue(),
            'dotted': False,
            'directional': False,
        }
    ]

    data = utils.prepare_model_relations(anyapp_models.Language)
    assert data == []  # no arrow duplicates from another side


def test_self_referencing_1_n():
    data = utils.prepare_model_relations(anyapp_models.Category)
    assert data == [
        {
            'start_label': 'n',
            'end_label': '1',
            'start_obj': anyapp_models.Category,
            'end_obj': anyapp_models.Category,
            'start_field': utils.get_model_field_by_name(anyapp_models.Category, 'parent'),
            'end_field': utils.get_model_pk_field(anyapp_models.Category),
            'color': AnyValue(),
            'dotted': False,
            'directional': True,
        }
    ]


def test_self_referencing_n_n():
    data = utils.prepare_model_relations(anyapp_models.Friend)
    assert data == [
        {
            'start_label': 'n',
            'end_label': 'n',
            'start_obj': anyapp_models.Friend,
            'end_obj': anyapp_models.Friend,
            'start_field': utils.get_model_field_by_name(anyapp_models.Friend, 'friends'),
            'end_field': utils.get_model_pk_field(anyapp_models.Friend),
            'color': AnyValue(),
            'dotted': False,
            'directional': False,
        }
    ]


def test_relations_n_n_through():
    assert len(utils.get_model_m2m_fields(anyapp_models.Picture)) == 0
    assert len(utils.get_model_m2m_fields(anyapp_models.Poster)) == 1
    assert len(utils.get_model_m2m_fields(anyapp_models.Like)) == 0
    # pk, created_at, picture, poster
    assert len(utils.prepare_model_fields(anyapp_models.Like)) == 4

    data = utils.prepare_model_relations(anyapp_models.Poster)
    assert data == []
    data = utils.prepare_model_relations(anyapp_models.Picture)
    assert data == []
    data = utils.prepare_model_relations(anyapp_models.Like)
    assert data == [
        {
            'start_label': 'n',
            'end_label': '1',
            'start_obj': anyapp_models.Like,
            'end_obj': anyapp_models.Poster,
            'start_field': utils.get_model_field_by_name(anyapp_models.Like, 'poster'),
            'end_field': utils.get_model_pk_field(anyapp_models.Poster),
            'color': AnyValue(),
            'dotted': False,
            'directional': True,
        },
        {
            'start_label': 'n',
            'end_label': '1',
            'start_obj': anyapp_models.Like,
            'end_obj': anyapp_models.Picture,
            'start_field': utils.get_model_field_by_name(anyapp_models.Like, 'picture'),
            'end_field': utils.get_model_pk_field(anyapp_models.Picture),
            'color': AnyValue(),
            'dotted': False,
            'directional': True,
        },
    ]


def test_relation_from_abstract_model():
    data = utils.prepare_model_relations(anyapp_models.AbstractGoods)
    assert data == [
        {
            'start_label': 'n',
            'end_label': '1',
            'start_obj': anyapp_models.AbstractGoods,
            'end_obj': anyapp_models.Shop,
            'start_field': utils.get_model_field_by_name(anyapp_models.AbstractGoods, 'shop'),
            'end_field': utils.get_model_pk_field(anyapp_models.Shop),
            'color': AnyValue(),
            'dotted': False,
            'directional': True,
        }
    ]
    data = utils.prepare_model_relations(anyapp_models.GroceryGoods)
    assert data == []


def test_prepare_model_inheritance():
    f = utils.prepare_model_inheritance

    data = f(anyapp_models.Dog)
    assert data == [
        {
            'start_label': '',
            'end_label': 'multi-table',
            'start_obj': anyapp_models.Dog,
            'end_obj': anyapp_models.Pet,
            'dotted': True,
            'directional': True,
            'color': AnyValue(),
        }
    ]

    data = f(anyapp_models.Circle)
    assert data == [
        {
            'start_label': '',
            'end_label': 'abstract',
            'start_obj': anyapp_models.Circle,
            'end_obj': anyapp_models.AbstractShape,
            'dotted': True,
            'directional': True,
            'color': AnyValue(),
        }
    ]

    data = f(anyapp_models.ProxyShop)
    assert data == [
        {
            'start_label': '',
            'end_label': 'proxy',
            'start_obj': anyapp_models.ProxyShop,
            'end_obj': anyapp_models.Shop,
            'dotted': True,
            'directional': True,
            'color': AnyValue(),
        }
    ]

    data = f(anyapp_models.Engine)
    assert data == []
