#!/bin/bash

echo "=== LakeB2B SlideSmith Starting ==="
echo "PORT=${PORT:-8000}"
echo "REDIS_URL is ${REDIS_URL:+set}${REDIS_URL:-unset}"
echo "PATH=$PATH"
echo "Python: $(which python 2>/dev/null || echo 'not found')"
echo "Uvicorn: $(which uvicorn 2>/dev/null || echo 'not found')"

# Activate virtual environment (ensures uvicorn/celery are in PATH)
if [ -f /opt/venv/bin/activate ]; then
    source /opt/venv/bin/activate
    echo "Venv activated. PATH=$PATH"
else
    echo "WARNING: /opt/venv/bin/activate not found"
fi

# Start Celery worker in background only if Redis is available
if [ -n "$REDIS_URL" ]; then
    echo "Starting Celery worker..."
    /opt/venv/bin/celery -A app.workers.tasks worker --concurrency=2 --loglevel=info &
else
    echo "REDIS_URL not set, skipping Celery worker"
fi

# Start FastAPI web server (foreground - keeps container alive)
echo "Starting FastAPI server on port ${PORT:-8000}..."
exec /opt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
