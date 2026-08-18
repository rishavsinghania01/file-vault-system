#!/bin/sh
set -e

# Ensure required directories exist and are writable
mkdir -p /app/data /app/media /app/staticfiles
chmod -R 777 /app/data /app/media /app/staticfiles

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Starting server..."
exec gunicorn --bind 0.0.0.0:8000 --workers 3 core.wsgi:application
