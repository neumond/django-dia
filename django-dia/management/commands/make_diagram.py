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
from importlib import import_module
import pkgutil

import six
import xml.etree.ElementTree as ET
from django.core.management.base import BaseCommand

utils = import_module('django-dia.utils')
get_full_model_list = utils.get_full_model_list
get_model_name = utils.get_model_name
get_model_relations = utils.prepare_model_relations
get_model_fields = utils.prepare_model_fields
get_model_inheritance = utils.prepare_model_inheritance
get_apps = utils.get_apps
get_app = utils.get_app
get_target_apps = utils.get_target_apps


def get_empty_xml():
    return pkgutil.get_data(__package__, 'empty.xml')


def parse_file_or_list(arg):
    if not arg:
        return []
    if ',' not in arg and os.path.isfile(arg):
        return [e.strip() for e in open(arg).readlines()]
    return arg.split(',')


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
    label = model._meta.app_label
    if label in app_colors:
        return app_colors[label]
    newcolor = get_rand_color()
    app_colors[label] = newcolor
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
    for i, frec in enumerate(modelrec['fields']):
        if frec['name'] == field.name:
            return i
    return None


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
                            help='Render output file.')
        parser.add_argument('--verbose-names', '-n', action='store_true', dest='verbose_names',
                            help='Use verbose_name of models and fields')
        parser.add_argument('--exclude-columns', '-x', action='store', dest='exclude_columns',
                            help='Exclude specific column(s) from the graph. Can also load exclude list from file.')
        parser.add_argument('--exclude-models', '-X', action='store', dest='exclude_models',
                            help='Exclude specific model(s) from the graph. Can also load exclude list from file.')
        parser.add_argument('--inheritance', '-e', action='store_true', dest='inheritance',
                            help='Include inheritance arrows')
        parser.add_argument('--disable-sort-fields', '-S', action="store_false", dest="sort_fields",
                            default=True, help="Do not sort fields")
        parser.add_argument('--bezier', action='store_true', dest='bezier',
                            help='Use bezier arrows instead of database relation arrows')

    def handle(self, *args, **options):
        self.verbose_names = options['verbose_names']
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

        model_list = get_full_model_list(
            get_target_apps(
                *options['appnames'],
                allapps=options['all_applications']
            ),
            exclude_fields=self.exclude_fields
        )
        for model in model_list:
            mdata = {
                'id': obj_num,
                'pos': (random.random() * 80, random.random() * 80),
                'name': get_model_name(model),
                'fields': get_model_fields(model),
                'color': get_model_color(app_colors, model),
                'port_idx': 0,
            }
            self.xml_make_table(mdata)
            obj_ref.append((obj_num, model, mdata))
            obj_num += 1

        for model in model_list:
            for rel in get_model_relations(model):
                try:
                    self.prepare_relation_stage2(obj_ref, rel, obj_num)
                    self.xml_make_relation(rel)
                    obj_num += 1
                except ModelNotFoundException:
                    pass
            if self.inheritance:
                for rel in get_model_inheritance(model):
                    try:
                        self.prepare_relation_stage2(obj_ref, rel, obj_num)
                        self.xml_make_relation(rel)
                    except ModelNotFoundException:
                        pass

        self.write_output(
            u'<?xml version="1.0" encoding="UTF-8"?>'.encode('utf-8') +
            ET.tostring(dom, encoding='utf-8'),
            options['outputfile']
        )

    def write_output(self, xml, outfile):
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
        idx = None if 'start_field' not in rel or rel['start_field'] is None or rel['start_field'].primary_key \
            else field_index(start_rec, rel['start_field'])
        rel['start_port'] = allocate_free_port(start_rec) if idx is None else 12 + idx * 2
        idx = None if 'end_field' not in rel or rel['end_field'] is None or rel['end_field'].primary_key \
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
