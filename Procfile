web: daphne -b 0.0.0.0 -p $PORT backend.asgi:application
worker: celery -A backend worker -l info
beat: celery -A backend beat -l info
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
