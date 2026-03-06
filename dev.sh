#!/bin/bash

echo "🚀 Starting FollowThrough DEV environment..."

PROJECT_DIR=~/FollowThrough

# -----------------------
# BACKEND TERMINAL
# -----------------------
osascript <<EOF
tell application "Terminal"
    do script "cd $PROJECT_DIR/backend && source venv/bin/activate && uvicorn main:app --reload"
end tell
EOF

# -----------------------
# FRONTEND TERMINAL
# -----------------------
osascript <<EOF
tell application "Terminal"
    do script "cd $PROJECT_DIR/followthrough-desktop && npm run tauri dev"
end tell
EOF

echo "✅ Backend and Desktop app launching..."