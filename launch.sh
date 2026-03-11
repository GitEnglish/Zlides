#!/bin/bash

# Zlides Launcher - starts backend and opens frontend

clear
echo "🚀 Starting Zlides..."
echo ""

# Load .env file properly
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Check if Z_AI_API_KEY is set
if [ -z "$Z_AI_API_KEY" ]; then
    echo "❌ Error: Z_AI_API_KEY is not set!"
    echo "Add it to .env file: echo 'Z_AI_API_KEY=your-key' >> .env"
    exit 1
fi

# Kill any existing server on port 8766
echo "🧹 Cleaning up old processes..."
lsof -ti:8766 | xargs kill -9 2>/dev/null || true
sleep 1

# Start HTTP server in background for frontend
echo "📱 Starting frontend server..."
pkill -f "http.server 8765" 2>/dev/null || true
python3 -m http.server 8765 > /dev/null 2>&1 &
sleep 1

echo "🌐 Starting backend server..."
echo "✅ Server running at http://localhost:8766"
echo "✅ Frontend at http://localhost:8765/index.html"
echo "Press Ctrl+C to stop"
echo ""

uv run python slide_server.py 2>&1 | grep --line-buffered -v "INFO:     127.0.0.1"
