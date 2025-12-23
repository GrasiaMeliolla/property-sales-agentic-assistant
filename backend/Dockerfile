FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Environment
ENV PORT=8000
ENV DJANGO_SETTINGS_MODULE=config.settings

# Run with gunicorn
CMD sh -c "\
    echo '=== Running migrations ===' && \
    python manage.py migrate --noinput && \
    echo '=== Starting gunicorn on port '\$PORT' ===' && \
    exec gunicorn config.wsgi:application --bind 0.0.0.0:\$PORT --workers 1 --timeout 120 --log-level info \
"
