set -e
cd $(dirname $0)
export PYTHONPATH="$(realpath .);$PYTHONPATH"
export DJANGO_PROJECT_SETTINGS=test_project.settings
cd test_project
python manage.py make_diagram -a -o ../scheme.dia
cd ..
dia --integrated scheme.dia
rm scheme.dia
