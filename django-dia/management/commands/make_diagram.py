# coding: utf-8
"""
Based on:
Django model to DOT (Graphviz) converter
  by Antonio Cavedoni <antonio@cavedoni.org>
django-extensions application code (graph_models command)
"""

import os
import gzip

from django.core.management.base import BaseCommand

from ... import utils, diagram


def parse_file_or_list(arg):
    if not arg:
        return set()
    if ',' not in arg and os.path.isfile(arg):
        with open(arg) as f:
            return {line.strip() for line in f.readlines()}
    return set(arg.split(','))


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
        parser.add_argument('--pretend', '-p', action='store_true', dest='pretend',
                            help='Output list of models in format suitable for exclusion options')
        parser.add_argument('--inheritance', '-e', action='store_true', dest='inheritance',
                            help='Include inheritance arrows')
        parser.add_argument('--disable-sort-fields', '-S', action="store_false", dest="sort_fields",
                            default=True, help="Do not sort fields")
        parser.add_argument('--bezier', action='store_true', dest='bezier',
                            help='Use bezier arrows instead of database relation arrows')

    def handle(self, *args, **options):
        model_list = utils.get_full_model_list(
            utils.get_target_apps(
                options['appnames'],
                allapps=options['all_applications']
            ),
            exclude_models=parse_file_or_list(options['exclude_models'])
        )

        if options['pretend']:
            for lbl in sorted(utils.get_model_label(m) for m in model_list):
                self.stdout.write(lbl)
            return

        self.verbose_names = options['verbose_names']
        self.exclude_fields = parse_file_or_list(options['exclude_columns'])
        self.sort_fields = options['sort_fields']

        tables, rels = diagram.prepare_data(model_list, inheritance=options['inheritance'])

        self.write_output(
            diagram.dia_xml(tables, rels, bezier=options['bezier']),
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
