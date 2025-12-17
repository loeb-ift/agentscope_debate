#!/bin/bash
set -e

# Start Celery Worker in background
echo "Starting Celery Worker..."
celery -A worker.celery_app worker --loglevel=info &

# Start FastAPI Server in foreground
echo "Starting FastAPI Server..."
uvicorn api.main:app --host 0.0.0.0 --port 8000