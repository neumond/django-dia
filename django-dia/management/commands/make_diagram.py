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
    attr = ET.SubElement(parent, 'dia:attribute', attrib={'name': name})

    textnode = False
    attribs = None
    if atype == 'boolean':
        value = 'true' if value else 'false'
    elif atype == 'string':
        value = u'#{}#'.format(value)
        textnode = True
    elif atype == 'real':
        value = '{:.18f}'.format(value)
    elif atype == 'enum':
        value = '{}'.format(value)
    elif atype == 'point':
        value = '{:.2f},{:.2f}'.format(*value)
    elif atype == 'rectangle':
        value = '{:.2f},{:.2f};{:.2f},{:.2f}'.format(*value)
    elif atype == 'color':
        value = '#' + value
    elif atype == 'font':
        attribs = {'family': unicode(value[0]), 'style': unicode(value[1]), 'name': unicode(value[2])}
    else:
        raise ValueError('Unknown type')

    if attribs is None:
        attribs = {}
    if not textnode and not attribs:
        attribs['val'] = value
    v = ET.SubElement(attr, 'dia:{}'.format(atype), attrib=attribs)
    if textnode:
        v.text = value


def get_rand_color():
    r = int(random.random() * 80) + 175
    g = int(random.random() * 80) + 175
    b = int(random.random() * 80) + 175
    return (hex(r)[-2:] + hex(g)[-2:] + hex(b)[-2:]).upper()


def get_model_color(app_colors, model):
    l = model._meta.app_label
    if l in app_colors:
        return app_colors[l]
    newcolor = get_rand_color()
    app_colors[l] = newcolor
    return newcolor


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

        ET.register_namespace('dia', 'http://www.lysator.liu.se/~alla/dia/')
        ns = {'dia': 'http://www.lysator.liu.se/~alla/dia/'}
        dom = ET.fromstring(render_to_string('django-dia/empty.xml', {}))
        self.layer = dom.find('dia:layer', namespaces=ns)

        app_colors = {}

        obj_num = 0
        obj_ref = []

        def find_model_data(obj_ref, model):
            for num, m, data in obj_ref:
                if model == m:
                    return data
            raise Exception('Model not found')

        def field_index(modelrec, field):
            for i, f in enumerate(modelrec['fields']):
                if field == f['field']:
                    return i
            return -1

        model_list = self.get_full_model_list(apps)
        for model in model_list:
            mdata = {
                'id': obj_num,
                'pos': (random.random() * 80, random.random() * 80),
                'name': self.get_model_name(model),
                'fields': self.get_model_fields(model),
                'color': get_model_color(app_colors, model),
            }
            self.xml_make_table(mdata)
            obj_ref.append((obj_num, model, mdata))
            obj_num += 1

        for model in model_list:
            for rel in self.get_model_relations(model):
                rel['id'] = obj_num
                start_rec = find_model_data(obj_ref, rel['start_obj'])
                end_rec = find_model_data(obj_ref, rel['end_obj'])
                rel['start_obj_id'] = start_rec['id']
                rel['end_obj_id'] = end_rec['id']
                rel['start_field_num'] = field_index(start_rec, rel['start_field'])
                rel['end_field_num'] = field_index(end_rec, rel['end_field'])
                self.xml_make_relation(rel)
                obj_num += 1


        print('<?xml version="1.0" encoding="UTF-8"?>')
        print(ET.tostring(dom, encoding='utf-8'))

    def xml_make_table(self, data):
        obj = ET.SubElement(self.layer, 'dia:object', attrib={
            'type': 'Database - Table',
            'version': '0',
            'id': 'O{}'.format(data['id']),
        })

        attr = ET.SubElement(obj, 'dia:attribute', attrib={'name': 'meta'})
        ET.SubElement(attr, 'dia:composite', attrib={'type': 'dict'})

        make_dia_attribute(obj, 'elem_corner', 'point', data['pos'])
        make_dia_attribute(obj, 'name', 'string', data['name'])
        make_dia_attribute(obj, 'visible_comment', 'boolean', False)
        make_dia_attribute(obj, 'tagging_comment', 'boolean', False)
        make_dia_attribute(obj, 'underline_primary_key', 'boolean', True)
        make_dia_attribute(obj, 'bold_primary_keys', 'boolean', False)

        make_dia_attribute(obj, 'normal_font', 'font', ('monospace', 0, 'Courier'))
        make_dia_attribute(obj, 'name_font', 'font', ('sans', 80, 'Helvetica-Bold'))
        make_dia_attribute(obj, 'comment_font', 'font', ('sans', 8, 'Helvetica-Oblique'))
        make_dia_attribute(obj, 'normal_font_height', 'real', 0.8)
        make_dia_attribute(obj, 'name_font_height', 'real', 0.7)
        make_dia_attribute(obj, 'comment_font_height', 'real', 0.7)

        make_dia_attribute(obj, 'line_width', 'real', 0.1)
        make_dia_attribute(obj, 'text_colour', 'color', '000000')
        make_dia_attribute(obj, 'line_colour', 'color', '000000')
        make_dia_attribute(obj, 'fill_colour', 'color', data['color'])

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

    def xml_make_relation(self, data):
        rel = ET.SubElement(self.layer, 'dia:object', attrib={
            'type': 'Database - Reference',
            'version': '0',
            'id': 'O{}'.format(data['id']),
        })

        make_dia_attribute(rel, 'start_point_desc', 'string', data['start_label'])
        make_dia_attribute(rel, 'end_point_desc', 'string', data['end_label'])

        conns = ET.SubElement(rel, 'dia:connections')
        ET.SubElement(conns, 'dia:connection', attrib={
            'handle': '0',
            'to': 'O{}'.format(data['end_obj_id']),
            'connection': unicode(12 + data['end_field_num'] * 2),
        })
        ET.SubElement(conns, 'dia:connection', attrib={
            'handle': '1',
            'to': 'O{}'.format(data['start_obj_id']),
            'connection': unicode(12 + data['start_field_num'] * 2),
        })

        attr = ET.SubElement(rel, 'dia:attribute', attrib={'name': 'line_style'})
        ET.SubElement(attr, 'dia:enum', attrib={'val': '4' if data['dotted'] else '0'})
        ET.SubElement(attr, 'dia:real', attrib={'val': '1'})

        make_dia_attribute(rel, 'corner_radius', 'real', 0)
        make_dia_attribute(rel, 'end_arrow', 'enum', 3 if data['directional'] else 0)
        make_dia_attribute(rel, 'end_arrow_length', 'real', 0.25)
        make_dia_attribute(rel, 'end_arrow_width', 'real', 0.25)
        make_dia_attribute(rel, 'normal_font', 'font', ('monospace', 0, 'Courier'))
        make_dia_attribute(rel, 'normal_font_height', 'real', 0.7)
        make_dia_attribute(rel, 'text_colour', 'color', '000000')
        make_dia_attribute(rel, 'line_colour', 'color', '000000')
        make_dia_attribute(rel, 'line_width', 'real', 0.1)
        make_dia_attribute(rel, 'orth_autoroute', 'boolean', True)

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

    def get_full_model_list(self, apps):
        result = []
        for app in apps:
            result.extend(get_app_models_with_abstracts(app))
        result = list(set(result))
        return filter(lambda model: self.get_model_name(model) not in self.exclude_fields, result)

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

    def prepare_field(self, field):
        return {
            'field': field,
            'name': field.name,
            'type': type(field).__name__,
            'comment': field.verbose_name,
            'primary_key': field.primary_key,
            'nullable': field.null,
            'unique': field.unique,
        }

    def get_model_fields(self, appmodel):
        result = []

        fields = appmodel._meta.local_fields

        # find primary key and print it first, ignoring implicit id if other pk exists
        pk = appmodel._meta.pk
        if pk and pk in fields and not appmodel._meta.abstract:
            result.append(self.prepare_field(pk))

        for field in fields:
            if self.get_field_name(field) in self.exclude_fields:
                continue
            if pk and field == pk:
                continue
            result.append(self.prepare_field(field))

        if self.sort_fields:
            result = sorted(result, key=lambda field: (not field['primary_key'], field['name']))

        return result

    def prepare_relation(self, field, start_label, end_label, dotted=False):
        # handle self-relationships and lazy-relationships
        if isinstance(field.rel.to, six.string_types):
            if field.rel.to == 'self':
                target_model = field.model
            else:
                raise Exception("Lazy relationship for model (%s) must be explicit for field (%s)" % (field.model.__name__, field.name))
        else:
            target_model = field.rel.to

        if hasattr(field.rel, 'field_name'):
            target_field = target_model._meta.get_field(field.rel.field_name)
        else:
            target_field = target_model._meta.pk

        if self.get_model_name(target_model) in self.exclude_models:
            return

        return {
            'start_label': start_label,
            'end_label': end_label,
            'start_obj': field.model,
            'end_obj': target_model,
            'start_field': field,
            'end_field': target_field,
            'dotted': dotted,
            'directional': start_label != end_label,
        }

    def get_model_relations(self, appmodel):
        result = []
        abstract_fields = get_model_abstract_fields(appmodel)

        for field in appmodel._meta.local_fields:
            if field.attname.endswith('_ptr_id'):  # excluding field redundant with inheritance relation
                continue
            if field in abstract_fields:  # excluding fields inherited from abstract classes. they too show as local_fields
                continue
            if self.get_field_name(field) in self.exclude_fields:
                continue
            if isinstance(field, OneToOneField):
                result.append(self.prepare_relation(field, '1', '1'))
            elif isinstance(field, ForeignKey):
                result.append(self.prepare_relation(field, '1', 'n'))

        for field in appmodel._meta.local_many_to_many:
            if self.get_field_name(field) in self.exclude_fields:
                continue
            if isinstance(field, ManyToManyField):
                if (getattr(field, 'creates_table', False) or  # django 1.1.
                    (hasattr(field.rel.through, '_meta') and field.rel.through._meta.auto_created)):  # django 1.2
                    result.append(self.prepare_relation(field, 'n', 'n'))
            elif isinstance(field, GenericRelation):
                result.append(self.prepare_relation(field, 'n', 'n', dotted=True))

        return [rel for rel in result if rel is not None]

    def get_inheritance_relations(self, model):
        result = []
        for parent in model.__bases__:
            if hasattr(parent, '_meta'):  # parent is a model
                add_inh(parent)
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

