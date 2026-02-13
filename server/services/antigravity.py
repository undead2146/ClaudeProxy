"""
Antigravity (Gemini proxy) process management.
"""

import os
import subprocess

from core.config import logger, ANTIGRAVITY_ENABLED, ANTIGRAVITY_PORT

# Antigravity process handle
antigravity_process = None


def start_antigravity_server():
    """Start the Antigravity proxy server as a subprocess."""
    global antigravity_process

    if not ANTIGRAVITY_ENABLED:
        logger.info("[Antigravity] Disabled - skipping startup")
        return

    try:
        # Find npx executable (Windows: npx.cmd, Unix: npx)
        npx_cmd = None
        possible_paths = [
            "npx",
            "npx.cmd",
            r"C:\Program Files\nodejs\npx.cmd",
            os.path.expanduser(r"~\AppData\Roaming\npm\npx.cmd"),
        ]

        for path in possible_paths:
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    npx_cmd = path
                    logger.info(f"[Antigravity] Found npx at: {path}")
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        if not npx_cmd:
            logger.error("[Antigravity] npx not found. Please ensure Node.js is installed and in PATH.")
            logger.info("[Antigravity] Try: refreshenv or restart terminal after installing Node.js")
            return

        node_check = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if node_check.returncode != 0:
            logger.error("[Antigravity] Node.js not found. Please install Node.js to use Antigravity.")
            return

        logger.info(f"[Antigravity] Node.js version: {node_check.stdout.strip()}")
        logger.info("[Antigravity] Skipping package version check...")
        logger.info(f"[Antigravity] Starting server on port {ANTIGRAVITY_PORT}...")

        env = os.environ.copy()
        env["PORT"] = str(ANTIGRAVITY_PORT)

        import time
        if os.name == 'nt':
            antigravity_process = subprocess.Popen(
                [npx_cmd, "antigravity-claude-proxy@latest", "start"],
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            antigravity_process = subprocess.Popen(
                [npx_cmd, "antigravity-claude-proxy@latest", "start"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

        # Wait for the server to start and verify it's responding
        max_wait = 15
        wait_interval = 1
        healthy = False

        for attempt in range(max_wait):
            time.sleep(wait_interval)

            if antigravity_process.poll() is not None:
                logger.error(f"[Antigravity] Process crashed during startup")
                return

            try:
                import httpx
                response = httpx.get(f"http://localhost:{ANTIGRAVITY_PORT}/health", timeout=2.0)
                if response.status_code == 200:
                    healthy = True
                    break
            except Exception:
                continue

        if healthy:
            logger.info(f"[Antigravity] Server started successfully on port {ANTIGRAVITY_PORT}")
        else:
            logger.warning(f"[Antigravity] Server process running but not responding on port {ANTIGRAVITY_PORT}")
            logger.warning("[Antigravity] Check that port is not blocked and npm cache is working")

    except FileNotFoundError:
        logger.error("[Antigravity] npx not found. Please install Node.js and npm.")
    except subprocess.TimeoutExpired:
        logger.warning("[Antigravity] Installation check timed out, proceeding anyway...")
    except Exception as e:
        logger.error(f"[Antigravity] Failed to start: {e}")


def stop_antigravity_server():
    """Stop the Antigravity proxy server."""
    global antigravity_process

    if antigravity_process:
        logger.info("[Antigravity] Stopping server...")
        antigravity_process.terminate()
        try:
            antigravity_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("[Antigravity] Force killing server...")
            antigravity_process.kill()
        antigravity_process = None
        logger.info("[Antigravity] Server stopped")
