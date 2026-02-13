#!/bin/bash
# Manage Claude Code Proxy, Antigravity Server, and GitHub Copilot API (Linux)

ACTION=${1:-status}
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

PID_FILE="$LOG_DIR/proxy.pid"
AG_PID_FILE="$LOG_DIR/antigravity.pid"
CP_PID_FILE="$LOG_DIR/copilot.pid"

start_antigravity() {
    if [ -f "$AG_PID_FILE" ]; then
        AG_PID=$(cat "$AG_PID_FILE")
        if ps -p "$AG_PID" > /dev/null; then
            echo "[Antigravity] Already running (PID: $AG_PID)"
            return
        fi
    fi

    echo "[Antigravity] Starting server on port 8081..."
    PORT=8081 nohup antigravity-claude-proxy start > "$LOG_DIR/antigravity.log" 2>&1 &
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
    start_antigravity
    start_copilot

    if [ -f "$PID_FILE" ]; then
        PROXY_PID=$(cat "$PID_FILE")
        if ps -p "$PROXY_PID" > /dev/null; then
            echo "[Proxy] Already running (PID: $PROXY_PID)"
            return
        fi
    fi

    echo "[Proxy] Starting server on port 8082..."
    cd "$PROJECT_ROOT/server"
    nohup python3 proxy.py > "$LOG_DIR/proxy.log" 2>&1 &
    PROXY_PID=$!
    echo $PROXY_PID > "$PID_FILE"
    echo "[Proxy] Started (PID: $PROXY_PID)"
    echo "Dashboard: http://localhost:8082/dashboard"
}

stop_all() {
    echo "Stopping all services..."
    [ -f "$PID_FILE" ] && kill $(cat "$PID_FILE") && rm "$PID_FILE"
    [ -f "$AG_PID_FILE" ] && kill $(cat "$AG_PID_FILE") && rm "$AG_PID_FILE"
    [ -f "$CP_PID_FILE" ] && kill $(cat "$CP_PID_FILE") && rm "$CP_PID_FILE"
    echo "All services stopped."
}

status() {
    echo "--- Service Status ---"
    for service in "Proxy:$PID_FILE" "Antigravity:$AG_PID_FILE" "Copilot:$CP_PID_FILE"; do
        NAME="${service%%:*}"
        FILE="${service#*:}"
        if [ -f "$FILE" ] && ps -p $(cat "$FILE") > /dev/null; then
            echo "$NAME: RUNNING (PID: $(cat "$FILE"))"
        else
            echo "$NAME: STOPPED"
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
esac
