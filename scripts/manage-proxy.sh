#!/bin/bash
# Manage Claude Code Proxy, Antigravity Server, and GitHub Copilot API (Linux)
# Usage: ./manage-proxy.sh {start|stop|restart|status}

# Detect python
if command -v python3 &>/dev/null; then
  PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
  PYTHON_CMD="python"
else
  echo "Error: Python not found."
  exit 1
fi

# Ensure standard paths are in PATH (fixes command not found issues on some VPS)
export PATH=$PATH:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Fix line endings using the python script (more robust than sed on Windows-edited files)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$PYTHON_CMD" "$SCRIPT_DIR/fix_line_endings.py" >/dev/null 2>&1 || true

ACTION=${1:-status}
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="$LOG_DIR/proxy.pid"
AG_PID_FILE="$LOG_DIR/antigravity.pid"
CP_PID_FILE="$LOG_DIR/copilot.pid"
CP_PID_FILE="$LOG_DIR/copilot.pid"

# Prefer python3 explicitly
PYTHON_CMD="python3"
if ! command -v "$PYTHON_CMD" &>/dev/null; then
    PYTHON_CMD="python"
fi

echo "Using Python: $PYTHON_CMD"

start_antigravity() {
    if [ -f "$AG_PID_FILE" ]; then
        AG_PID=$(cat "$AG_PID_FILE")
        if ps -p "$AG_PID" > /dev/null; then
            echo "[Antigravity] Already running (PID: $AG_PID)"
            return
        fi
    fi

    echo "[Antigravity] Starting server on port 8081..."
    PORT=8081 nohup npx antigravity-claude-proxy@latest start --port $PORT > "$LOG_DIR/antigravity.log" 2>&1 &
    AG_PID=$!
    echo $AG_PID > "$AG_PID_FILE"
    sleep 2
    echo "[Antigravity] Started (PID: $AG_PID)"
}

start_copilot() {
    if [ -f "$CP_PID_FILE" ]; then
        CP_PID=$(cat "$CP_PID_FILE")
        if ps -p "$CP_PID" > /dev/null; then
            echo "[Copilot] Already running (PID: $CP_PID)"
            return
        fi
    fi

    echo "[Copilot] Starting GitHub Copilot API on port 4141..."
    nohup npx copilot-api@latest start --port 4141 > "$LOG_DIR/copilot.log" 2>&1 &
    CP_PID=$!
    echo $CP_PID > "$CP_PID_FILE"
    sleep 2
    echo "[Copilot] Started (PID: $CP_PID)"
}

start_proxy() {
    if [ -f "$PID_FILE" ]; then
        PROXY_PID=$(cat "$PID_FILE")
        if ps -p "$PROXY_PID" > /dev/null; then
            echo "[Proxy] Already running (PID: $PROXY_PID)"
            return
        fi
    fi

    echo "[Proxy] Starting server on port 8082..."
    cd "$PROJECT_ROOT/server"
    # Add server directory to PYTHONPATH for subdirectory imports
    export PYTHONPATH="$PROJECT_ROOT/server:$PYTHONPATH"
    nohup "$PYTHON_CMD" proxy.py > "$LOG_DIR/proxy.log" 2>&1 &
    PROXY_PID=$!
    echo $PROXY_PID > "$PID_FILE"
    sleep 2
    echo "[Proxy] Started (PID: $PROXY_PID)"
    echo "Dashboard: http://localhost:8082/dashboard"
}

stop_all() {
    echo "Stopping all services..."
    if [ -f "$PID_FILE" ]; then
        kill $(cat "$PID_FILE") 2>/dev/null && rm "$PID_FILE"
    fi
    if [ -f "$AG_PID_FILE" ]; then
        kill $(cat "$AG_PID_FILE") 2>/dev/null && rm "$AG_PID_FILE"
    fi
    if [ -f "$CP_PID_FILE" ]; then
        kill $(cat "$CP_PID_FILE") 2>/dev/null && rm "$CP_PID_FILE"
    fi
    echo "All services stopped."
}

status() {
    echo "--- Service Status ---"
    for service in "Proxy:$PID_FILE" "Antigravity:$AG_PID_FILE" "Copilot:$CP_PID_FILE"; do
        NAME="${service%%:*}"
        FILE="${service#*:}"
        if [ -f "$FILE" ]; then
            if ps -p "$(cat "$FILE")" > /dev/null; then
                echo "$NAME: RUNNING (PID: $(cat "$FILE"))"
            else
                echo "$NAME: STOPPED"
            fi
        fi
        done
}

case "$ACTION" in
    start)
        start_proxy
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 1
        start_proxy
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
