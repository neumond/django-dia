from django.test import TestCase
from django.core.management import call_command
from django.utils.six import StringIO
import xml.etree.ElementTree as ET


class DjangoDiaTestCase(TestCase):
    def test_command_output(self):
        out = StringIO()
        call_command('make_diagram', all_applications=True, inheritance=True, stdout=out)
        line = out.getvalue()
        xml = ET.fromstring(line)
        ns = {'dia': 'http://www.lysator.liu.se/~alla/dia/'}
        assert len(xml.findall('./dia:layer/dia:object[@type=\'Database - Table\']', ns)) > 0
