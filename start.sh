#!/bin/sh
set -e

echo "🚀 Starting FollowThrough..."

# Ensure backend is treated as a proper module
export PYTHONPATH=/app

# Railway provides PORT dynamically
PORT="${PORT:-8080}"

echo "Using PORT=$PORT"
echo "PYTHONPATH=$PYTHONPATH"

# Start FastAPI correctly as a package
exec python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --proxy-headers \
  --forwarded-allow-ips="*"