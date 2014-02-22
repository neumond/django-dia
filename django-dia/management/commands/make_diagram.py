# coding: utf-8
"""
Based on:
Django model to DOT (Graphviz) converter
  by Antonio Cavedoni <antonio@cavedoni.org>
django-extensions application code (graph_models command)
"""

from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
import json
import xml.etree.ElementTree as ET
import random


import os
import six
import datetime
from django.utils.translation import activate as activate_language
from django.utils.safestring import mark_safe
from django.template import Context, loader, Template
from django.template.loader import render_to_string
from django.db import models
from django.db.models import get_models
from django.db.models.fields.related import ForeignKey, OneToOneField, ManyToManyField, RelatedField

try:
    from django.db.models.fields.generic import GenericRelation
    assert GenericRelation
except ImportError:
    from django.contrib.contenttypes.generic import GenericRelation


def parse_file_or_list(arg):
    if not arg:
        return []
    if not ',' in arg and os.path.isfile(arg):
        return [e.strip() for e in open(arg).readlines()]
    return arg.split(',')


def get_app_models_with_abstracts(app):
    appmodels = get_models(app)
    abstract_models = []
    for appmodel in appmodels:
        abstract_models = abstract_models + [abstract_model for abstract_model in appmodel.__bases__
                                             if hasattr(abstract_model, '_meta') and abstract_model._meta.abstract]
    abstract_models = list(set(abstract_models))  # remove duplicates
    return abstract_models + appmodels


def get_model_abstract_fields(model):
    result = []
    for e in model.__bases__:
        if hasattr(e, '_meta') and e._meta.abstract:
            result.extend(e._meta.fields)
            result.extend(get_model_abstract_fields(e))
    return result


def make_dia_attribute(parent, name, atype, value):
    textnode = False
    if atype == 'boolean':
        value = 'true' if value else 'false'
    elif atype == 'string':
        value = u'#{}#'.format(value)
        textnode = True
    elif atype == 'real':
        value = '{:.18f}'.format(value)
    elif atype == 'point':
        value = '{:.2f},{:.2f}'.format(*value)
    elif atype == 'rectangle':
        value = '{:.2f},{:.2f};{:.2f},{:.2f}'.format(*value)
    elif atype == 'color':
        value = '#' + value
    else:
        raise ValueError('Unknown type')
    attr = ET.SubElement(parent, 'dia:attribute', attrib={'name': name})
    a = {}
    if not textnode:
        a['val'] = value
    v = ET.SubElement(attr, 'dia:{}'.format(atype), attrib=a)
    if textnode:
        v.text = value


class Command(BaseCommand):
    help = 'Generate .dia diagram of your django project\'s models'
    args = '[appname]'
    option_list = BaseCommand.option_list + (
        #make_option('--disable-fields', '-d', action='store_true', dest='disable_fields',
                    #help='Do not show the class member fields'),
        #make_option('--group-models', '-g', action='store_true', dest='group_models',
                    #help='Group models together respective to their application'),
        make_option('--all-applications', '-a', action='store_true', dest='all_applications',
                    help='Automatically include all applications from INSTALLED_APPS'),
        make_option('--output', '-o', action='store', dest='outputfile',
                    help='Render output file.'),
        make_option('--verbose-names', '-n', action='store_true', dest='verbose_names',
                    help='Use verbose_name of models and fields'),
        #make_option('--language', '-L', action='store', dest='language',
                    #help='Specify language used for verbose_name localization'),
        make_option('--exclude-columns', '-x', action='store', dest='exclude_columns',
                    help='Exclude specific column(s) from the graph. Can also load exclude list from file.'),
        make_option('--exclude-models', '-X', action='store', dest='exclude_models',
                    help='Exclude specific model(s) from the graph. Can also load exclude list from file.'),
        make_option('--inheritance', '-e', action='store_true', dest='inheritance', default=True,
                    help='Include inheritance arrows (default)'),
        make_option('--no-inheritance', '-E', action='store_false', dest='inheritance',
                    help='Do not include inheritance arrows'),
        make_option('--hide-relations-from-fields', '-R', action='store_false', dest="relations_as_fields",
                    default=True, help="Do not show relations as fields in the graph."),
        make_option('--disable-sort-fields', '-S', action="store_false", dest="sort_fields",
                    default=True, help="Do not sort fields"),
    )

    def handle(self, *args, **options):
        apps = []
        if options['all_applications']:
            apps = models.get_apps()

        for app_label in args:
            app = models.get_app(app_label)
            if not app in apps:
                apps.append(app)

        self.verbose_names = options['verbose_names']
        self.exclude_models = parse_file_or_list(options['exclude_models'])
        self.exclude_fields = parse_file_or_list(options['exclude_columns'])
        self.inheritance = options['inheritance']
        self.sort_fields = options['sort_fields']

        data = []
        for app in apps:
            data.extend(self.get_app_data(app))

        ET.register_namespace('dia', 'http://www.lysator.liu.se/~alla/dia/')
        ns = {'dia': 'http://www.lysator.liu.se/~alla/dia/'}
        dom = ET.fromstring(render_to_string('django-dia/empty.xml', {}))
        self.layer = dom.find('dia:layer', namespaces=ns)

        for model_num, model in enumerate(data):
            f = []
            for field in model['fields']:
                ff = {
                    'name': field['name'],
                    'type': field['type'],
                    'comment': field['comment'],
                    'primary_key': field['primary_key'],
                    'nullable': field['null'],
                    'unique': False, # TODO:
                }
                f.append(ff)
            self.xml_make_table({
                'id': model_num,
                'pos': (random.random() * 40, random.random() * 40),
                'name': model['name'],
                'fields': f,
            })

        print(ET.tostring(dom, encoding='utf-8'))

    def xml_make_table(self, data):
        obj = ET.SubElement(self.layer, 'dia:object', attrib={
            'type': 'Database - Table',
            'version': '0',
            'id': 'O{}'.format(data['id']),
        })

        make_dia_attribute(obj, 'elem_corner', 'point', data['pos'])
        make_dia_attribute(obj, 'name', 'string', data['name'])

        attr = ET.SubElement(obj, 'dia:attribute', attrib={'name': 'attributes'})
        for field in data['fields']:
            self.xml_make_field(attr, field)

    def xml_make_field(self, parent, data):
        field = ET.SubElement(parent, 'dia:composite', attrib={'type': 'table_attribute'})

        xs = (
            ('name', 'string'),
            ('type', 'string'),
            ('comment', 'string'),
            ('primary_key', 'boolean'),
            ('nullable', 'boolean'),
            ('unique', 'boolean'),
        )

        for name, atype in xs:
            make_dia_attribute(field, name, atype, data[name])

    def get_field_name(self, field):
        return field.verbose_name if self.verbose_names and field.verbose_name else field.name

    def get_model_name(self, model):
        return model._meta.object_name

    def get_app_data(self, app):
        models = get_app_models_with_abstracts(app)
        result = []
        for model in models:
            if self.get_model_name(model) in self.exclude_models:
                continue
            result.append(self.get_model_data(model))
        return result

    def get_model_data(self, appmodel):
        appmodel_abstracts = [abstract_model.__name__ for abstract_model in appmodel.__bases__
                              if hasattr(abstract_model, '_meta') and abstract_model._meta.abstract]
        return {
            'app_name': appmodel.__module__.replace(".", "_"),
            'name': appmodel.__name__,
            'abstracts': appmodel_abstracts,
            'fields': self.get_model_fields(appmodel),
            'relations': self.get_model_relations(appmodel),
        }

    def prepare_field(self, field, abstract_fields):
        #label = self.get_field_name(field)
        if self.verbose_names and field.verbose_name:
            # TODO: bytes?
            label = field.verbose_name.decode("utf8")
            if label.islower():
                label = label.capitalize()
        else:
            label = field.name

        t = type(field).__name__
        if isinstance(field, (OneToOneField, ForeignKey)):
            t += " ({0})".format(field.rel.field_name)
        # TODO: ManyToManyField, GenericRelation

        return {
            'name': field.name,
            'comment': field.verbose_name,
            'label': label, # TODO:
            'type': t,
            'blank': field.blank,
            'null': field.null,
            'abstract': field in abstract_fields,
            'relation': isinstance(field, RelatedField),
            'primary_key': field.primary_key,
        }

    def get_model_fields(self, appmodel):
        result = []

        fields = appmodel._meta.local_fields
        abstract_fields = get_model_abstract_fields(appmodel)

        # find primary key and print it first, ignoring implicit id if other pk exists
        pk = appmodel._meta.pk
        if pk and not appmodel._meta.abstract and pk in fields:
            result.append(self.prepare_field(pk, abstract_fields))

        for field in fields:
            if self.get_field_name(field) in self.exclude_fields:
                continue
            if pk and field == pk:
                continue
            result.append(self.prepare_field(field, abstract_fields))

        if self.sort_fields:
            result = sorted(result, key=lambda field: (not field['primary_key'], not field['relation'], field['label']))

        return result

    def prepare_relation(self, field, extras):
        # TODO: same field name formatting
        if self.verbose_names and field.verbose_name:
            label = field.verbose_name.decode("utf8")
            if label.islower():
                label = label.capitalize()
        else:
            label = field.name

        # show related field name
        if hasattr(field, 'related_query_name'):
            related_query_name = field.related_query_name()
            if self.verbose_names and related_query_name.islower():
                related_query_name = related_query_name.replace('_', ' ').capitalize()
            label += ' (%s)' % related_query_name

        # handle self-relationships and lazy-relationships
        if isinstance(field.rel.to, six.string_types):
            if field.rel.to == 'self':
                target_model = field.model
            else:
                raise Exception("Lazy relationship for model (%s) must be explicit for field (%s)" % (field.model.__name__, field.name))
        else:
            target_model = field.rel.to

        return {
            'target_app': target_model.__module__.replace('.', '_'),
            'target': target_model.__name__,
            'type': type(field).__name__,
            'name': field.name,
            'label': label,
            'arrows': extras,
            'needs_node': True
        }

    def get_model_relations(self, appmodel):
        result = []
        abstract_fields = get_model_abstract_fields(appmodel)

        def _add(rel):
            if rel not in result and rel['target'] not in self.exclude_models:
                result.append(rel)

        def add(field, extras=''):
            rel = self.prepare_relation(field, extras)
            _add(rel)

        for field in appmodel._meta.local_fields:
            if field.attname.endswith('_ptr_id'):  # excluding field redundant with inheritance relation
                continue
            if field in abstract_fields:  # excluding fields inherited from abstract classes. they too show as local_fields
                continue
            if self.get_field_name(field) in self.exclude_fields:
                continue
            if isinstance(field, OneToOneField):
                add(field, '[arrowhead=none, arrowtail=none, dir=both]')
            elif isinstance(field, ForeignKey):
                add(field, '[arrowhead=none, arrowtail=dot, dir=both]')

        for field in appmodel._meta.local_many_to_many:
            if self.get_field_name(field) in self.exclude_fields:
                continue
            if isinstance(field, ManyToManyField):
                if (getattr(field, 'creates_table', False) or  # django 1.1.
                    (hasattr(field.rel.through, '_meta') and field.rel.through._meta.auto_created)):  # django 1.2
                    add(field, '[arrowhead=dot arrowtail=dot, dir=both]')
            elif isinstance(field, GenericRelation):
                add(field, mark_safe('[style="dotted", arrowhead=normal, arrowtail=normal, dir=both]'))

        def add_inh(parent):
            l = 'multi-table'
            if parent._meta.abstract:
                l = 'abstract'
            if appmodel._meta.proxy:
                l = 'proxy'
            l += r"\ninheritance"
            rel = {
                'target_app': parent.__module__.replace(".", "_"),
                'target': parent.__name__,
                'type': "inheritance",
                'name': "inheritance",
                'label': l,
                'arrows': '[arrowhead=empty, arrowtail=none, dir=both]',
                'needs_node': True,
            }
            # TODO: seems as if abstract models aren't part of models.getModels, which is why they are printed by this without any attributes.
            _add(rel)

        if self.inheritance:
            # add inheritance arrows
            for parent in appmodel.__bases__:
                if hasattr(parent, '_meta'):  # parent is a model
                    add_inh(parent)

        return result
