#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import signal

def get_paths():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    log_dir = os.path.join(project_root, "logs")
    pid_file = os.path.join(log_dir, "proxy.pid")
    ag_pid_file = os.path.join(log_dir, "antigravity.pid")
    cp_pid_file = os.path.join(log_dir, "copilot.pid")

    return project_root, log_dir, pid_file, ag_pid_file, cp_pid_file

def start_proxy():
    project_root, log_dir, pid_file, _, _ = get_paths()

    # Check if running
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            print(f"[Proxy] Already running (PID: {pid})")
            return
        except (OSError, ValueError):
            os.remove(pid_file)

    print("[Proxy] Starting server on port 8082...")

    # Check if port 8082 is free (basic check, allow proxy.py to do heavy lifting)
    # actually proxy.py handles it now.

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{os.path.join(project_root, 'server')}:{env.get('PYTHONPATH', '')}"

    # Use subprocess.Popen to detach
    log_file = open(os.path.join(log_dir, "proxy.log"), "a")

    server_script = os.path.join(project_root, "server", "proxy.py")

    proc = subprocess.Popen(
        [sys.executable, server_script],
        cwd=os.path.join(project_root, "server"),
        env=env,
        stdout=log_file,
        stderr=log_file,
        preexec_fn=os.setpgrp
    )

    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    print(f"[Proxy] Started (PID: {proc.pid})")
    print("Dashboard: http://localhost:8082/dashboard")
    time.sleep(1)

def stop_all():
    _, _, pid_file, ag_pid_file, cp_pid_file = get_paths()

    def kill_pid_file(path, name):
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    pid = int(f.read().strip())
                print(f"Stopping {name} (PID: {pid})...")
                os.kill(pid, signal.SIGTERM)
                # Wait a bit?
            except (OSError, ValueError) as e:
                print(f"Error stopping {name}: {e}")
            finally:
                if os.path.exists(path):
                    os.remove(path)

    kill_pid_file(pid_file, "Proxy")
    kill_pid_file(ag_pid_file, "Antigravity")
    kill_pid_file(cp_pid_file, "Copilot")

    print("All services stopped.")

def status():
    _, _, pid_file, ag_pid_file, cp_pid_file = get_paths()

    def check(path, name):
        state = "STOPPED"
        pid = ""
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                state = f"RUNNING (PID: {pid})"
            except OSError:
                state = "STOPPED (Stale PID file)"
            except ValueError:
                state = "STOPPED (Corrupt PID file)"
        print(f"{name}: {state}")

    print("--- Service Status ---")
    check(pid_file, "Proxy")
    check(ag_pid_file, "Antigravity")
    check(cp_pid_file, "Copilot")

def main():
    if len(sys.argv) < 2:
        action = "status"
    else:
        action = sys.argv[1]

    if action == "start":
        start_proxy()
    elif action == "stop":
        stop_all()
    elif action == "restart":
        stop_all()
        time.sleep(1)
        start_proxy()
    elif action == "status":
        status()
    else:
        print("Usage: python3 manage_proxy.py {start|stop|restart|status}")
        sys.exit(1)

if __name__ == "__main__":
    main()
