#!/bin/bash

# Zlides Launcher
BACKEND_PORT=2828
FRONTEND_PORT=2827

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

# ── Kill anything on our ports ───────────────────────────────────────────────
echo "Cleaning up old processes..."

kill_port() {
    local port=$1
    local pids
    pids=$(lsof -ti:"$port" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "  Killing processes on port $port: $pids"
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
        pids=$(lsof -ti:"$port" 2>/dev/null)
        if [ -n "$pids" ]; then
            echo "  Force retry on port $port..."
            echo "$pids" | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
    fi
}

kill_port "$FRONTEND_PORT"
kill_port "$BACKEND_PORT"

# Also kill by process name
pkill -9 -f "slide_server.py" 2>/dev/null || true
pkill -9 -f "http.server $FRONTEND_PORT" 2>/dev/null || true
sleep 1

# Verify ports are free
if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Error: Port $BACKEND_PORT still in use after cleanup!"
    exit 1
fi
if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Error: Port $FRONTEND_PORT still in use after cleanup!"
    exit 1
fi

# ── PIDs for cleanup ─────────────────────────────────────────────────────────
FRONTEND_PID=""
BACKEND_PID=""

cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    sleep 1
    [ -n "$BACKEND_PID" ] && kill -9 "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill -9 "$FRONTEND_PID" 2>/dev/null
    exit 0
}
trap cleanup INT TERM EXIT

# ── Start frontend ───────────────────────────────────────────────────────────
echo "Starting frontend server..."
python3 -m http.server "$FRONTEND_PORT" &>/dev/null &
FRONTEND_PID=$!
sleep 1

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "Error: Frontend server failed to start!"
    exit 1
fi

# ── Start backend ────────────────────────────────────────────────────────────
echo "Starting backend server..."
uv run python slide_server.py 2>&1 &
BACKEND_PID=$!

sleep 2
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Error: Backend server failed to start!"
    exit 1
fi

echo ""
echo "Server running at http://localhost:$BACKEND_PORT"
echo "Frontend at http://localhost:$FRONTEND_PORT/index.html"
echo "Press Ctrl+C to stop"
echo ""

wait "$BACKEND_PID"
