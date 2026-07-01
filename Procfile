release: python manage.py migrate && python manage.py collectstatic --noinput
web: gunicorn corralon_nicola.wsgi --log-file -
