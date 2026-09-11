# Image de production pour Farm Control (Flask + Gunicorn + WeasyPrint).
FROM python:3.12-slim

# Dependances systeme requises par WeasyPrint (Pango/Cairo/GDK-Pixbuf) et psycopg2.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads

ENV FLASK_APP=wsgi.py \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Applique les migrations puis demarre Gunicorn (2 workers, adapte au tier gratuit).
CMD ["sh", "-c", "flask db upgrade && gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 wsgi:app"]
