#!/bin/bash

# Activate virtual environment
source /opt/venv/bin/activate

# Start Celery worker in background only if Redis is available
if [ -n "$REDIS_URL" ]; then
    echo "Starting Celery worker..."
    celery -A app.workers.tasks worker --concurrency=2 --loglevel=info &
else
    echo "REDIS_URL not set, skipping Celery worker"
fi

# Start FastAPI web server (foreground - keeps container alive)
echo "Starting FastAPI server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
