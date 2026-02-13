#!/bin/bash
# Claude Proxy systemd Installation Script
# This script installs Claude Proxy as a systemd service on Linux.

set -e

# Fix CRLF line endings in this script (in case it was uploaded from Windows)
sed -i 's/\r$//' "${BASH_SOURCE[0]}" 2>/dev/null || true

# Check for root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Get project root (2 levels up from scripts/ dir)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Determine Python command
if command -v python3 &>/dev/null; then
  PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
  PYTHON_CMD="python"
else
  echo "Error: Neither python3 nor python found in PATH"
  exit 1
fi

echo "Using Python: $PYTHON_CMD"

USER_HOME=$(getent passwd "$USER" | cut -d: -f7)
SERVICE_FILE="/etc/systemd/system/claude-proxy.service"

echo "--- Claude Proxy Daemon Installer (Linux) ---"

# Create log directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# Fix CRLF line endings in other scripts
sed -i 's/\r$//' "$PROJECT_ROOT/scripts/manage-proxy.sh"
sed -i 's/\r$//' "$PROJECT_ROOT/server/proxy.py"

# Ensure scripts are executable
chmod +x "$PROJECT_ROOT/scripts/manage-proxy.sh"
chmod +x "$PROJECT_ROOT/server/proxy.py"

# Create systemd service file
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Claude Code Proxy Daemon
After=network.target

[Service]
Type=forking
User=$USER_NAME
WorkingDirectory=$PROJECT_ROOT
ExecStart=$PROJECT_ROOT/scripts/manage-proxy.sh start
ExecStop=$PROJECT_ROOT/scripts/manage-proxy.sh stop
PIDFile=$PROJECT_ROOT/logs/proxy.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable claude-proxy
systemctl start claude-proxy

echo "Success! Claude Proxy has been installed as a systemd service."
echo "Status: systemctl status claude-proxy"
echo "Logs: tail -f $PROJECT_ROOT/logs/proxy.log"
echo "To stop: sudo systemctl stop claude-proxy"
echo "To uninstall: sudo systemctl disable claude-proxy && sudo rm $SERVICE_FILE"
