#!/bin/bash
# Claude Proxy systemd Installation Script
# This script installs the Claude Proxy as a systemd service on Linux.

set -e

# Check for root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
USER_NAME=$(logname || echo $SUDO_USER)
SERVICE_FILE="/etc/systemd/system/claude-proxy.service"

echo "--- Claude Proxy Daemon Installer (Linux) ---"

# Create log directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"
chown -R "$USER_NAME:$USER_NAME" "$PROJECT_ROOT/logs"

# Ensure scripts are executable
chmod +x "$PROJECT_ROOT/scripts/manage-proxy.sh"
chmod +x "$PROJECT_ROOT/server/proxy.py"

# Create systemd service file
cat <<EOF > "$SERVICE_FILE"
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
