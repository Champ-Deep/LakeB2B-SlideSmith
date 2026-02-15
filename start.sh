#!/bin/bash

# Activate virtual environment
source /opt/venv/bin/activate

# Start FastAPI web server (single process - tasks run in background threads)
echo "Starting FastAPI server on port ${PORT:-8080}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
