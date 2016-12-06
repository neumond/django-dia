# coding: utf-8
"""
Based on:
Django model to DOT (Graphviz) converter
  by Antonio Cavedoni <antonio@cavedoni.org>
django-extensions application code (graph_models command)
"""

import os
import random
import gzip
from distutils.version import StrictVersion

import six
import xml.etree.ElementTree as ET
from django.core.management.base import BaseCommand
from django.db.models.fields.related import ForeignKey, OneToOneField, ManyToManyField
from django import get_version

DJANGO_VERSION = get_version()
if StrictVersion(DJANGO_VERSION) >= StrictVersion('1.9'):
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


_EMPTY_XML = None


def get_empty_xml():
    global _EMPTY_XML
    if _EMPTY_XML is None:
        from os.path import abspath, join, dirname
        with open(join(dirname(abspath(__file__)), 'empty.xml')) as f:
            _EMPTY_XML = f.read()
    return _EMPTY_XML


def parse_file_or_list(arg):
    if not arg:
        return []
    if ',' not in arg and os.path.isfile(arg):
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
        attribs = {
            'family': six.text_type(value[0]),
            'style': six.text_type(value[1]),
            'name': six.text_type(value[2])
        }
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


class ModelNotFoundException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def find_model_data(obj_ref, model):
    for num, m, data in obj_ref:
        if model == m:
            return data
    raise ModelNotFoundException("No model '%s' in %s" % (repr(model), repr([m for num, m, data in obj_ref])))


def field_index(modelrec, field):
    for i, f in enumerate(modelrec['fields']):
        if field == f['field']:
            return i
    return None  # ManyToManyFields


def allocate_free_port(modelrec):
    result = allocate_free_port.port_order[modelrec['port_idx']]
    modelrec['port_idx'] += 1
    if modelrec['port_idx'] >= len(allocate_free_port.port_order):
        modelrec['port_idx'] = 0
    return result


allocate_free_port.port_order = [2, 1, 3, 9, 8, 10]

# 0 - 1 - 2 - 3 - 4
# 5    title      6
# -----------------
# 12             13
# 14             15
#      ...
# 7 - 8 - 9 -10 -11


class Command(BaseCommand):
    help = 'Generate .dia diagram of your django project\'s models'

    def add_arguments(self, parser):
        parser.add_argument('appnames', metavar='appname', nargs='*',
                            help='Names of particular applications')
        parser.add_argument('--all-applications', '-a', action='store_true', dest='all_applications',
                            help='Automatically include all applications from INSTALLED_APPS')
        parser.add_argument('--output', '-o', action='store', dest='outputfile',
                            help='Render output file.'),
        parser.add_argument('--verbose-names', '-n', action='store_true', dest='verbose_names',
                            help='Use verbose_name of models and fields'),
        parser.add_argument('--exclude-columns', '-x', action='store', dest='exclude_columns',
                            help='Exclude specific column(s) from the graph. Can also load exclude list from file.'),
        parser.add_argument('--exclude-models', '-X', action='store', dest='exclude_models',
                            help='Exclude specific model(s) from the graph. Can also load exclude list from file.'),
        parser.add_argument('--exclude-modules', '-M', action='store', dest='exclude_modules',
                            help='Exclude specific module(s) from the graph. Can also load exclude list from file.'),
        parser.add_argument('--inheritance', '-e', action='store_true', dest='inheritance',
                            help='Include inheritance arrows'),
        parser.add_argument('--disable-sort-fields', '-S', action="store_false", dest="sort_fields",
                            default=True, help="Do not sort fields"),
        parser.add_argument('--bezier', action='store_true', dest='bezier',
                            help='Use bezier arrows instead of database relation arrows'),

    def handle(self, *args, **options):
        apps = []
        if options['all_applications']:
            apps = list(get_apps())

        for app_label in options['appnames']:
            app = get_app(app_label)
            if app not in apps:
                apps.append(app)

        self.verbose_names = options['verbose_names']
        self.exclude_modules = parse_file_or_list(options['exclude_modules'])
        self.exclude_models = parse_file_or_list(options['exclude_models'])
        self.exclude_fields = parse_file_or_list(options['exclude_columns'])
        self.inheritance = options['inheritance']
        self.sort_fields = options['sort_fields']
        self.bezier = options['bezier']

        ET.register_namespace('dia', 'http://www.lysator.liu.se/~alla/dia/')
        ns = {'dia': 'http://www.lysator.liu.se/~alla/dia/'}
        dom = ET.fromstring(get_empty_xml())
        self.layer = dom.find('dia:layer', namespaces=ns)

        app_colors = {}

        obj_num = 0
        obj_ref = []

        model_list = self.get_full_model_list(apps)
        for model in model_list:
            mdata = {
                'id': obj_num,
                'pos': (random.random() * 80, random.random() * 80),
                'name': self.get_model_name(model),
                'fields': self.get_model_fields(model),
                'color': get_model_color(app_colors, model),
                'port_idx': 0,
            }
            self.xml_make_table(mdata)
            obj_ref.append((obj_num, model, mdata))
            obj_num += 1

        for model in model_list:
            for rel in self.get_model_relations(model):
                try:
                    self.prepare_relation_stage2(obj_ref, rel, obj_num)
                    self.xml_make_relation(rel)
                    obj_num += 1
                except ModelNotFoundException:
                    pass
            if self.inheritance:
                for rel in self.get_model_inheritance(model):
                    try:
                        self.prepare_relation_stage2(obj_ref, rel, obj_num)
                        self.xml_make_relation(rel)
                    except ModelNotFoundException:
                        pass

        xml = six.b('<?xml version="1.0" encoding="UTF-8"?>') + \
            ET.tostring(dom, encoding='utf-8')

        outfile = options['outputfile']
        if outfile:
            if outfile[-4:] != '.dia':
                outfile += '.dia'
            with gzip.open(outfile, 'wb') as f:
                f.write(xml)
        else:
            self.stdout.write(xml.decode('utf-8'))

    def prepare_relation_stage2(self, obj_ref, rel, num):
        rel['id'] = num
        start_rec = find_model_data(obj_ref, rel['start_obj'])
        end_rec = find_model_data(obj_ref, rel['end_obj'])
        rel['start_obj_id'] = start_rec['id']
        rel['end_obj_id'] = end_rec['id']

        idx = None if 'start_field' not in rel or rel['start_field'].primary_key\
            else field_index(start_rec, rel['start_field'])
        rel['start_port'] = allocate_free_port(start_rec) if idx is None else 12 + idx * 2

        idx = None if 'end_field' not in rel or rel['end_field'].primary_key\
            else field_index(end_rec, rel['end_field'])
        rel['end_port'] = allocate_free_port(end_rec) if idx is None else 12 + idx * 2

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
            'type': 'Standard - BezierLine' if self.bezier else 'Database - Reference',
            'version': '0',
            'id': 'O{}'.format(data['id']),
        })

        line_style = '4' if data['dotted'] else '0'
        if self.bezier:
            make_dia_attribute(rel, 'line_style', 'enum', line_style)
            attr = ET.SubElement(rel, 'dia:attribute', attrib={'name': 'corner_types'})
            ET.SubElement(attr, 'dia:enum', attrib={'val': '0'})
            ET.SubElement(attr, 'dia:enum', attrib={'val': '0'})
            attr = ET.SubElement(rel, 'dia:attribute', attrib={'name': 'bez_points'})
            ET.SubElement(attr, 'dia:point', attrib={'val': '0.0,0.0'})
            ET.SubElement(attr, 'dia:point', attrib={'val': '0.0,0.0'})
            ET.SubElement(attr, 'dia:point', attrib={'val': '0.0,0.0'})
            ET.SubElement(attr, 'dia:point', attrib={'val': '0.0,0.0'})
        else:
            attr = ET.SubElement(rel, 'dia:attribute', attrib={'name': 'line_style'})
            ET.SubElement(attr, 'dia:enum', attrib={'val': line_style})
            ET.SubElement(attr, 'dia:real', attrib={'val': '1'})

            make_dia_attribute(rel, 'start_point_desc', 'string', data['start_label'])
            make_dia_attribute(rel, 'end_point_desc', 'string', data['end_label'])
            make_dia_attribute(rel, 'corner_radius', 'real', 0)
            make_dia_attribute(rel, 'normal_font', 'font', ('monospace', 0, 'Courier'))
            make_dia_attribute(rel, 'normal_font_height', 'real', 0.7)
            make_dia_attribute(rel, 'text_colour', 'color', data['color'])
            make_dia_attribute(rel, 'orth_autoroute', 'boolean', True)

        conns = ET.SubElement(rel, 'dia:connections')
        ET.SubElement(conns, 'dia:connection', attrib={
            'handle': '0',
            'to': 'O{}'.format(data['end_obj_id']),
            'connection': six.text_type(data['end_port']),
        })
        ET.SubElement(conns, 'dia:connection', attrib={
            'handle': '3' if self.bezier else '1',
            'to': 'O{}'.format(data['start_obj_id']),
            'connection': six.text_type(data['start_port']),
        })

        make_dia_attribute(rel, 'end_arrow', 'enum', 3 if data['directional'] else 0)
        make_dia_attribute(rel, 'end_arrow_length', 'real', 0.25)
        make_dia_attribute(rel, 'end_arrow_width', 'real', 0.25)
        make_dia_attribute(rel, 'line_colour', 'color', data['color'])
        make_dia_attribute(rel, 'line_width', 'real', 0.1)

    def get_field_name(self, field):
        return field.verbose_name if self.verbose_names and field.verbose_name else field.name

    def get_model_name(self, model):
        return model._meta.object_name

    def get_full_model_list(self, apps):
        result = []
        for app in apps:
            result.extend(get_app_models_with_abstracts(app))

        result = list(set(result))
        if self.exclude_modules:
            result = list(filter(lambda model:  model.__module__ not in self.exclude_modules, result))
        if self.exclude_fields:
            result = list(filter(lambda model: self.get_model_name(model) not in self.exclude_fields, result))

        return result

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
            elif field.rel.to == 'auth.User':
                from django.contrib.auth import get_user_model
                target_model = get_user_model()
            elif field.rel.to == 'sites.Site':
                from django.contrib.sites.models import Site
                target_model = Site
            else:
                raise Exception('Lazy relationship for model ({}) must be explicit for field ({})'
                                .format(field.model.__name__, field.name))
        else:
            target_model = field.rel.to

        if getattr(field.rel, 'field_name', None):
                target_field = target_model._meta.get_field(field.rel.field_name)
        else:
            target_field = target_model._meta.pk

        if self.get_model_name(target_model) in self.exclude_models:
            return

        color = '000000'
        if start_label == '1' and end_label == '1':
            color = 'E2A639'
        if start_label == 'n' and end_label == 'n':
            color = '75A908'

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

    def get_model_relations(self, appmodel):
        result = []
        abstract_fields = get_model_abstract_fields(appmodel)

        for field in appmodel._meta.local_fields:
            if field.attname.endswith('_ptr_id'):  # excluding field redundant with inheritance relation
                continue
            if field in abstract_fields:
                # excluding fields inherited from abstract classes. they too show as local_fields
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

    def get_model_inheritance(self, model):
        result = []
        for parent in model.__bases__:
            if hasattr(parent, '_meta'):  # parent is a model
                l = 'multi-table'
                if parent._meta.abstract:
                    l = 'abstract'
                if model._meta.proxy:
                    l = 'proxy'
                result.append({
                    'start_label': '',
                    'end_label': l,
                    'start_obj': model,
                    'end_obj': parent,
                    'dotted': True,
                    'directional': True,
                    'color': '000000',
                })
        return result
        # TODO: seems as if abstract models aren't part of models.getModels,
        # which is why they are printed by this without any attributes.
