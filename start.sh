#!/bin/bash

echo "🚀 Starting FollowThrough..."

cd backend

# activate virtual environment
source venv/bin/activate

echo "✅ Virtual environment activated"

# kill anything using port 8000
echo "🧹 Clearing old server..."
lsof -ti:8000 | xargs kill -9 2>/dev/null

# start backend
echo "⚡ Launching API..."
uvicorn main:app --reload