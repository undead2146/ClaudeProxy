#!/bin/bash
# Cloudflare Tunnel Startup Script for Linux/VPS
# This script manages the Cloudflare tunnel for the proxy server

TUNNEL_LOG="tunnel.log"
TUNNEL_URL_FILE="TUNNEL_URL.txt"
PROXY_PORT="8082"
CLOUDFLARED_BIN="./cloudflared"

echo "=========================================="
echo "Cloudflare Tunnel Manager"
echo "=========================================="
echo ""

# Function to check if cloudflared is installed
check_cloudflared() {
    if [ ! -f "$CLOUDFLARED_BIN" ]; then
        echo "cloudflared not found. Downloading..."

        # Detect architecture
        ARCH=$(uname -m)
        OS=$(uname -s | tr '[:upper:]' '[:lower:]')

        if [ "$OS" = "linux" ]; then
            if [ "$ARCH" = "x86_64" ]; then
                wget -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
            elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
                wget -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64
            else
                echo "Unsupported architecture: $ARCH"
                exit 1
            fi
            chmod +x cloudflared
            CLOUDFLARED_BIN="./cloudflared"
        else
            echo "Please install cloudflared manually for your OS: $OS"
            exit 1
        fi
    fi
}

# Function to kill existing cloudflared processes
kill_existing() {
    echo "Stopping any existing cloudflared processes..."
    pkill -f cloudflared 2>/dev/null
    sleep 2
}

# Function to start tunnel
start_tunnel() {
    echo "Starting Cloudflare tunnel..."
    echo "Proxy URL: http://localhost:$PROXY_PORT"
    echo ""

    # Start tunnel in background
    nohup $CLOUDFLARED_BIN tunnel --url http://localhost:$PROXY_PORT --logfile $TUNNEL_LOG > /dev/null 2>&1 &

    # Wait for tunnel to establish
    echo "Waiting for tunnel to establish (15 seconds)..."
    sleep 15

    # Extract URL from log
    TUNNEL_URL=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" $TUNNEL_LOG | tail -1)

    if [ -n "$TUNNEL_URL" ]; then
        echo "$TUNNEL_URL" > $TUNNEL_URL_FILE
        echo ""
        echo "=========================================="
        echo " TUNNEL IS ACTIVE!"
        echo "=========================================="
        echo "URL: $TUNNEL_URL"
        echo "=========================================="
        echo ""
        echo "Tunnel is running in background."
        echo "Log file: $TUNNEL_LOG"
        echo "URL file: $TUNNEL_URL_FILE"
        echo ""
        echo "To stop: pkill -f cloudflared"
        echo "To check status: curl $TUNNEL_URL/health"
        return 0
    else
        echo ""
        echo "WARNING: Could not extract tunnel URL from log."
        echo "Check $TUNNEL_LOG for details."
        return 1
    fi
}

# Function to check tunnel status
check_status() {
    if pgrep -f cloudflared > /dev/null; then
        echo " Cloudflared is running"

        if [ -f "$TUNNEL_URL_FILE" ]; then
            TUNNEL_URL=$(cat $TUNNEL_URL_FILE)
            echo " Tunnel URL: $TUNNEL_URL"

            # Test connectivity
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $TUNNEL_URL/health 2>/dev/null)
            if [ "$HTTP_CODE" = "200" ]; then
                echo " Tunnel is responding (HTTP $HTTP_CODE)"
                return 0
            else
                echo " Tunnel not responding (HTTP $HTTP_CODE)"
                return 1
            fi
        else
            echo " Tunnel URL file not found"
            return 1
        fi
    else
        echo " Cloudflared is not running"
        return 1
    fi
}

# Main script logic
case "${1:-start}" in
    start)
        check_cloudflared
        kill_existing
        start_tunnel
        ;;
    stop)
        kill_existing
        echo "Tunnel stopped."
        ;;
    restart)
        check_cloudflared
        kill_existing
        start_tunnel
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
