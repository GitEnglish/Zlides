#!/bin/bash

# Zlides Launcher
PORT=2828

clear
echo "Starting Zlides..."
echo ""

# Load .env file
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Check API key
if [ -z "$Z_AI_API_KEY" ]; then
    echo "Error: Z_AI_API_KEY is not set!"
    echo "Add it to .env file: echo 'Z_AI_API_KEY=your-key' >> .env"
    exit 1
fi

# ── Kill anything on our port ──────────────────────────────────────────────
echo "Cleaning up old processes..."
pids=$(lsof -ti:"$PORT" 2>/dev/null)
if [ -n "$pids" ]; then
    echo "  Killing processes on port $PORT: $pids"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

pkill -9 -f "slide_server.py" 2>/dev/null || true
sleep 1

if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Error: Port $PORT still in use after cleanup!"
    exit 1
fi

# ── Trap cleanup ───────────────────────────────────────────────────────────
BACKEND_PID=""

cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    sleep 1
    [ -n "$BACKEND_PID" ] && kill -9 "$BACKEND_PID" 2>/dev/null
    exit 0
}
trap cleanup INT TERM EXIT

# ── Start server ───────────────────────────────────────────────────────────
echo "Starting server..."
uv run python slide_server.py 2>&1 &
BACKEND_PID=$!

sleep 2
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Error: Server failed to start!"
    exit 1
fi

echo ""
echo "Zlides running at http://localhost:$PORT"
echo "Press Ctrl+C to stop"
echo ""

# Auto-open browser
sleep 1
xdg-open "http://localhost:$PORT" 2>/dev/null &

wait "$BACKEND_PID"
