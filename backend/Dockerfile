FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput \
    && useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_demo --if-empty && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --access-logfile -"]
