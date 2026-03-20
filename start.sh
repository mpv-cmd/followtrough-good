#!/usr/bin/env bash
set -e

cd /app
export PYTHONPATH=/app

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8080}"