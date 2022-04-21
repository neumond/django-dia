import six
import xml.etree.ElementTree as ET
import pkgutil
import random
from itertools import count, cycle
from functools import partial

from . import utils


XML_NAMESPACES = {'dia': 'http://www.lysator.liu.se/~alla/dia/'}

for k, v in six.iteritems(XML_NAMESPACES):
    ET.register_namespace(k, v)


# Preparation ==============


# 0 - 1 - 2 - 3 - 4
# 5    title      6
# -----------------
# 12             13
# 14             15
#      ...
# 7 - 8 - 9 -10 -11

PORT_ORDER = (2, 1, 3, 9, 8, 10)


def get_field_port(field_idx):
    return 12 + field_idx * 2


def get_rand_color():
    r = int(random.random() * 80) + 175
    g = int(random.random() * 80) + 175
    b = int(random.random() * 80) + 175
    return (hex(r)[-2:] + hex(g)[-2:] + hex(b)[-2:]).upper()


class ModelColors:
    def __init__(self):
        self.colors = {}

    def get(self, model):
        label = utils.get_model_applabel(model)
        if label not in self.colors:
            self.colors[label] = get_rand_color()
        return self.colors[label]


def get_port_index(field, mdata):
    if field is None or field.primary_key:
        return next(mdata['ports'])
    return get_field_port(mdata['field_to_index'][field.name])


def prepare_relation_stage2(model_to_mdata, obj_num, rel):
    start_rec = model_to_mdata[rel['start_obj']]
    end_rec = model_to_mdata[rel['end_obj']]
    rel.update({
        'id': next(obj_num),
        'start_obj_id': start_rec['id'],
        'end_obj_id': end_rec['id'],
        'start_port': get_port_index(rel.get('start_field', None), start_rec),
        'end_port': get_port_index(rel.get('end_field', None), end_rec),
    })
    return rel


def prepare_data(model_list, inheritance=False):
    model_colors = ModelColors()
    obj_num = count()
    model_data = []
    model_to_mdata = {}

    for model in model_list:
        mdata = {
            'id': next(obj_num),
            'pos': (random.random() * 80, random.random() * 80),
            'name': utils.get_model_name(model),
            'fields': utils.prepare_model_fields(model),
            'color': model_colors.get(model),
            'ports': cycle(PORT_ORDER),
        }
        mdata['field_to_index'] = {f['name']: i for i, f in enumerate(mdata['fields'])}
        model_to_mdata[model] = mdata
        model_data.append(mdata)

    rel_stage2 = partial(prepare_relation_stage2, model_to_mdata, obj_num)
    rel_data = []

    for model in model_list:
        for rel in utils.prepare_model_relations(model):
            try:
                rel_data.append(rel_stage2(rel))
            except KeyError:
                pass
        if inheritance:
            for rel in utils.prepare_model_inheritance(model):
                try:
                    rel_data.append(rel_stage2(rel))
                except KeyError:
                    pass

    for mdata in model_data:
        del mdata['ports']
        del mdata['field_to_index']
    for rel in rel_data:
        del rel['start_obj']
        del rel['end_obj']
        rel.pop('start_field', None)
        rel.pop('end_field', None)

    # at this point all data is JSON-serializable
    # and contains no objects

    return model_data, rel_data


# XML generation ===========


def make_dia_attribute(name, atype, value):
    attr = ET.Element('dia:attribute', attrib={'name': name})

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

    return attr


def xml_make_field(data):
    field = ET.Element('dia:composite', attrib={'type': 'table_attribute'})
    xs = (
        ('name', 'string'),
        ('type', 'string'),
        ('comment', 'string'),
        ('primary_key', 'boolean'),
        ('nullable', 'boolean'),
        ('unique', 'boolean'),
    )
    for name, atype in xs:
        field.append(make_dia_attribute(name, atype, data[name]))
    return field


def xml_make_table(data):
    obj = ET.Element('dia:object', attrib={
        'type': 'Database - Table',
        'version': '0',
        'id': 'O{}'.format(data['id']),
    })

    attr = ET.SubElement(obj, 'dia:attribute', attrib={'name': 'meta'})
    ET.SubElement(attr, 'dia:composite', attrib={'type': 'dict'})

    obj.extend([
        make_dia_attribute('elem_corner', 'point', data['pos']),
        make_dia_attribute('name', 'string', data['name']),
        make_dia_attribute('visible_comment', 'boolean', False),
        make_dia_attribute('tagging_comment', 'boolean', False),
        make_dia_attribute('underline_primary_key', 'boolean', True),
        make_dia_attribute('bold_primary_keys', 'boolean', False),

        make_dia_attribute('normal_font', 'font', ('monospace', 0, 'Courier')),
        make_dia_attribute('name_font', 'font', ('sans', 80, 'Helvetica-Bold')),
        make_dia_attribute('comment_font', 'font', ('sans', 8, 'Helvetica-Oblique')),
        make_dia_attribute('normal_font_height', 'real', 0.8),
        make_dia_attribute('name_font_height', 'real', 0.7),
        make_dia_attribute('comment_font_height', 'real', 0.7),

        make_dia_attribute('line_width', 'real', 0.1),
        make_dia_attribute('text_colour', 'color', '000000'),
        make_dia_attribute('line_colour', 'color', '000000'),
        make_dia_attribute('fill_colour', 'color', data['color']),
    ])

    attr = ET.SubElement(obj, 'dia:attribute', attrib={'name': 'attributes'})
    for field in data['fields']:
        attr.append(xml_make_field(field))

    return obj


def xml_make_relation(data, bezier=False):
    rel = ET.Element('dia:object', attrib={
        'type': 'Standard - BezierLine' if bezier else 'Database - Reference',
        'version': '0',
        'id': 'O{}'.format(data['id']),
    })

    line_style = '4' if data['dotted'] else '0'
    if bezier:
        rel.append(make_dia_attribute('line_style', 'enum', line_style))
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

        rel.extend([
            make_dia_attribute('start_point_desc', 'string', data['start_label']),
            make_dia_attribute('end_point_desc', 'string', data['end_label']),
            make_dia_attribute('corner_radius', 'real', 0),
            make_dia_attribute('normal_font', 'font', ('monospace', 0, 'Courier')),
            make_dia_attribute('normal_font_height', 'real', 0.7),
            make_dia_attribute('text_colour', 'color', data['color']),
            make_dia_attribute('orth_autoroute', 'boolean', True),
        ])

    conns = ET.SubElement(rel, 'dia:connections')
    ET.SubElement(conns, 'dia:connection', attrib={
        'handle': '0',
        'to': 'O{}'.format(data['start_obj_id']),
        'connection': six.text_type(data['start_port']),
    })
    ET.SubElement(conns, 'dia:connection', attrib={
        'handle': '3' if bezier else '1',
        'to': 'O{}'.format(data['end_obj_id']),
        'connection': six.text_type(data['end_port']),
    })

    rel.extend([
        make_dia_attribute('end_arrow', 'enum', 3 if data['directional'] else 0),
        make_dia_attribute('end_arrow_length', 'real', 0.25),
        make_dia_attribute('end_arrow_width', 'real', 0.25),
        make_dia_attribute('line_colour', 'color', data['color']),
        make_dia_attribute('line_width', 'real', 0.1),
    ])

    return rel


def get_empty_xml():
    return pkgutil.get_data(__package__, 'empty.xml')


def dia_xml(tables, rels, bezier=False):
    dom = ET.fromstring(get_empty_xml())
    layer = dom.find('dia:layer', namespaces=XML_NAMESPACES)

    for t in tables:
        layer.append(xml_make_table(t))
    for r in rels:
        layer.append(xml_make_relation(r, bezier=bezier))

    return (
        u'<?xml version="1.0" encoding="UTF-8"?>'.encode('utf-8') +
        ET.tostring(dom, encoding='utf-8')
    )
