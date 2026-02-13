#!/usr/bin/env python3
import os
import sys
import subprocess
import getpass

def main():
    if os.geteuid() != 0:
        print("Please run as root (use sudo)")
        sys.exit(1)

    # Get project root (2 levels up from scripts/ dir)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    print(f"Project Root: {project_root}")

    # Determine Python command
    python_cmd = sys.executable
    print(f"Using Python: {python_cmd}")

    user_name = os.getenv('SUDO_USER') or getpass.getuser()
    print(f"Installing as user: {user_name}")

    service_file_path = "/etc/systemd/system/claude-proxy.service"

    print("--- Claude Proxy Daemon Installer (Linux/Python) ---")

    # Create log directory if it doesn't exist
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Create systemd service file content
    # Note: We use the python script for management now to avoid shebang issues
    manage_script = os.path.join(script_dir, "manage_proxy.py")

    service_content = f"""[Unit]
Description=Claude Code Proxy Daemon
After=network.target

[Service]
Type=forking
User={user_name}
WorkingDirectory={project_root}
ExecStart={python_cmd} {manage_script} start
ExecStop={python_cmd} {manage_script} stop
PIDFile={os.path.join(log_dir, "proxy.pid")}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    print(f"Writing service file to {service_file_path}...")
    with open(service_file_path, "w") as f:
        f.write(service_content)

    # Reload systemd and enable service
    print("Reloading systemd...")
    subprocess.run(["systemctl", "daemon-reload"], check=True)

    print("Enabling claude-proxy service...")
    subprocess.run(["systemctl", "enable", "claude-proxy"], check=True)

    print("Starting claude-proxy service...")
    subprocess.run(["systemctl", "restart", "claude-proxy"], check=True)

    print("\nSuccess! Claude Proxy has been installed as a systemd service.")
    print("Status: systemctl status claude-proxy")
    print(f"Logs: tail -f {os.path.join(log_dir, 'proxy.log')}")
    print("To stop: sudo systemctl stop claude-proxy")
    print(f"To uninstall: sudo systemctl disable claude-proxy && sudo rm {service_file_path}")

if __name__ == "__main__":
    main()
