import xml.etree.ElementTree as ET
from io import StringIO

from django.core.management import call_command
from django.core.checks import run_checks


def test_django_model_checks():
    errors = run_checks()
    assert errors == []


def call_cmd(**opts):
    out = StringIO()
    call_command('make_diagram', stdout=out, **opts)
    return out.getvalue()


def test_command_output():
    line = call_cmd(all_applications=True, inheritance=True)
    xml = ET.fromstring(line)
    ns = {'dia': 'http://www.lysator.liu.se/~alla/dia/'}
    assert len(xml.findall('./dia:layer/dia:object[@type=\'Database - Table\']', ns)) > 0


def test_pretend():
    lines = call_cmd(all_applications=True, pretend=True).splitlines()
    assert len(lines) > 0
    assert 'anyapp.Shop' in lines

    lines = call_cmd(all_applications=True, pretend=True, exclude_models='anyapp.Shop,anyapp.Cat').splitlines()
    assert len(lines) > 0
    assert 'anyapp.Shop' not in lines
