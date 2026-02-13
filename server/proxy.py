#!/usr/bin/env python3
"""
Claude Code Proxy - Unified Router for Z.AI, Antigravity (Gemini), Anthropic, Copilot & more.

This is the application entry point. All logic lives in the sibling modules:
  config.py       — env vars, logger, runtime config
  middleware.py    — API key authentication
  oauth.py        — Anthropic OAuth token management
  routing.py      — provider selection per model tier
  sanitize.py     — payload cleaning & thinking-block helpers
  convert.py      — Anthropic ↔ OpenAI format conversion
  providers.py    — per-provider HTTP proxy functions
  antigravity.py  — Antigravity subprocess management
  endpoints.py    — all HTTP route handlers
  token_tracker.py — token usage persistence
"""

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.middleware import Middleware

from core.config import (
    logger, load_config, PROXY_PORT,
    ANTIGRAVITY_ENABLED, ANTIGRAVITY_PORT,
    ANTIGRAVITY_SONNET_MODEL, ANTIGRAVITY_HAIKU_MODEL, ANTIGRAVITY_OPUS_MODEL,
    ZAI_SONNET_MODEL, ZAI_HAIKU_MODEL, ZAI_OPUS_MODEL,
    GITHUB_COPILOT_SONNET_MODEL, GITHUB_COPILOT_HAIKU_MODEL, GITHUB_COPILOT_OPUS_MODEL,
    PROXY_API_KEY,
    get_sonnet_provider, get_haiku_provider, get_opus_provider,
)
from core.middleware import APIKeyMiddleware
from core.oauth import get_oauth_token
from services.antigravity import start_antigravity_server, stop_antigravity_server
from api.endpoints import (
    messages_endpoint,
    count_tokens_endpoint,
    health_check,
    get_config_endpoint,
    update_config_endpoint,
    get_favorites_endpoint,
    save_favorite_endpoint,
    delete_favorite_endpoint,
    get_logs_endpoint,
    clear_logs_endpoint,
    logs_page_endpoint,
    usage_page_endpoint,
    get_usage_stats_endpoint,
    reset_usage_stats_endpoint,
    test_antigravity_endpoint,
    copilot_usage_proxy,
    antigravity_health_proxy,
    dashboard_endpoint,
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
routes = [
    Route("/v1/messages", messages_endpoint, methods=["POST"]),
    Route("/v1/messages/count_tokens", count_tokens_endpoint, methods=["POST"]),
    Route("/health", health_check, methods=["GET"]),
    Route("/config", get_config_endpoint, methods=["GET"]),
    Route("/config", update_config_endpoint, methods=["POST"]),
    Route("/favorites", get_favorites_endpoint, methods=["GET"]),
    Route("/favorites", save_favorite_endpoint, methods=["POST"]),
    Route("/favorites/{idx}", delete_favorite_endpoint, methods=["DELETE"]),
    Route("/logs", get_logs_endpoint, methods=["GET"]),
    Route("/logs/clear", clear_logs_endpoint, methods=["POST"]),
    Route("/logs.html", logs_page_endpoint, methods=["GET"]),
    Route("/usage", usage_page_endpoint, methods=["GET"]),
    Route("/api/usage/stats", get_usage_stats_endpoint, methods=["GET"]),
    Route("/api/usage/reset", reset_usage_stats_endpoint, methods=["POST"]),
    Route("/api/copilot/usage", copilot_usage_proxy, methods=["GET"]),
    Route("/api/antigravity/health", antigravity_health_proxy, methods=["GET"]),
    Route("/test-antigravity", test_antigravity_endpoint, methods=["GET"]),
    Route("/dashboard", dashboard_endpoint, methods=["GET"]),
    Route("/", dashboard_endpoint, methods=["GET"]),
]

middleware = [
    Middleware(APIKeyMiddleware)
]

app = Starlette(debug=True, routes=routes, middleware=middleware)

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    import atexit
    import signal
    import subprocess
    import sys

    # Load configuration from file
    load_config()

    logger.info("=" * 70)
    logger.info("Claude Code Proxy - Unified Router (Z.AI + Gemini + Anthropic + Copilot)")
    logger.info("=" * 70)

    # Show routing configuration
    def get_model_display(provider, tier):
        if provider == "antigravity":
            model_map = {
                "Sonnet": ANTIGRAVITY_SONNET_MODEL,
                "Haiku": ANTIGRAVITY_HAIKU_MODEL,
                "Opus": ANTIGRAVITY_OPUS_MODEL
            }
            return f"Antigravity ({model_map.get(tier, 'unknown')})"
        elif provider == "glm" or provider == "zai":
            model_map = {
                "Sonnet": ZAI_SONNET_MODEL or "not configured",
                "Haiku": ZAI_HAIKU_MODEL or "not configured",
                "Opus": ZAI_OPUS_MODEL or "not configured"
            }
            return f"Z.AI ({model_map.get(tier, 'unknown')})"
        elif provider == "copilot":
            model_map = {
                "Sonnet": GITHUB_COPILOT_SONNET_MODEL,
                "Haiku": GITHUB_COPILOT_HAIKU_MODEL,
                "Opus": GITHUB_COPILOT_OPUS_MODEL
            }
            return f"GitHub Copilot ({model_map.get(tier, 'unknown')})"
        else:
            return "Anthropic (OAuth)"

    logger.info("Current Routing Configuration:")
    logger.info(f"  Sonnet → {get_model_display(get_sonnet_provider(), 'Sonnet')}")
    logger.info(f"  Haiku  → {get_model_display(get_haiku_provider(), 'Haiku')}")
    logger.info(f"  Opus   → {get_model_display(get_opus_provider(), 'Opus')}")

    if ANTIGRAVITY_ENABLED:
        logger.info("=" * 70)
        logger.info("Antigravity Server:")
        logger.info(f"  Status: Enabled")
        logger.info(f"  Port: {ANTIGRAVITY_PORT}")
        logger.info(f"  Dashboard: http://localhost:{ANTIGRAVITY_PORT}")
    else:
        logger.info(f"Antigravity: Disabled")

    oauth_token = get_oauth_token()
    current_providers = [get_sonnet_provider(), get_haiku_provider(), get_opus_provider()]
    if "anthropic" in current_providers:
        logger.info(f"Anthropic OAuth: {'Available ✓' if oauth_token else 'NOT FOUND ✗'}")

    if PROXY_API_KEY:
        logger.info("Authentication: ENABLED (API Key required)")
    else:
        logger.info("Authentication: DISABLED (Warning: Server is open to everyone)")

    logger.info("=" * 70)
    logger.info(f"Proxy listening on http://0.0.0.0:{PROXY_PORT}")
    logger.info(f"Configuration Dashboard: http://localhost:{PROXY_PORT}/dashboard")
    logger.info(f"Health check: http://localhost:{PROXY_PORT}/health")
    logger.info(f"API endpoint: http://localhost:{PROXY_PORT}/v1/messages")
    logger.info("=" * 70)

    # Start Antigravity if enabled
    if ANTIGRAVITY_ENABLED:
        start_antigravity_server()

    # Register cleanup handlers
    def cleanup():
        stop_antigravity_server()

    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: cleanup())
    signal.signal(signal.SIGINT, lambda s, f: cleanup())

    try:
        # Check and kill any process using the port
        def kill_process_on_port(port):
            """Find and kill any process listening on the specified port, excluding self."""
            logger.info(f"Checking for existing processes on port {port}...")

            pids_to_kill = set()
            my_pid = os.getpid()

            # Methods to find PIDs
            methods = []

            # Method 1: lsof
            def check_lsof():
                try:
                    # -t: terse (PIDs only)
                    # -i: internet files
                    output = subprocess.check_output(["lsof", "-t", f"-i:{port}"], stderr=subprocess.DEVNULL).decode().strip()
                    if output:
                        return [int(p) for p in output.split() if p.strip().isdigit()]
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
                return []
            methods.append(check_lsof)

            # Method 2: ss (socket statistics)
            def check_ss():
                try:
                    # -lptn: listening, processes, tcp, numeric
                    # output format: State Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
                    output = subprocess.check_output(["ss", "-lptn", f"sport = :{port}"], stderr=subprocess.DEVNULL).decode().strip()
                    found_pids = []
                    for line in output.splitlines():
                        if f":{port}" in line:
                            # Extract pid=1234 from "users:(("python",pid=1234,fd=3))"
                            parts = line.split("pid=")
                            for part in parts[1:]:
                                pid_str = part.split(",")[0]
                                if pid_str.isdigit():
                                    found_pids.append(int(pid_str))
                    return found_pids
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
                return []
            methods.append(check_ss)

            # Method 3: netstat (fallback)
            def check_netstat():
                try:
                    # -lnp: listening, numeric, program
                    output = subprocess.check_output(["netstat", "-lnp"], stderr=subprocess.DEVNULL).decode().strip()
                    found_pids = []
                    for line in output.splitlines():
                        if f":{port} " in line:
                            # tcp 0 0 0.0.0.0:8082 0.0.0.0:* LISTEN 1234/python
                            parts = line.split()
                            for part in parts:
                                if "/" in part and part.split("/")[0].isdigit():
                                    found_pids.append(int(part.split("/")[0]))
                    return found_pids
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
                return []
            methods.append(check_netstat)

            # Execute checks
            for method in methods:
                try:
                    pids = method()
                    for pid in pids:
                        if pid != my_pid:
                            pids_to_kill.add(pid)
                except Exception as e:
                    logger.debug(f"Port check method failed: {e}")

            if not pids_to_kill:
                logger.info(f"No conflicting processes found on port {port}.")
                return

            logger.info(f"Found conflicting PIDs on port {port}: {pids_to_kill}")

            for pid in pids_to_kill:
                logger.info(f"Killing process {pid} to free port {port}...")
                try:
                    os.kill(pid, signal.SIGKILL)
                    logger.info(f"Killed process {pid}.")
                except ProcessLookupError:
                    logger.info(f"Process {pid} already gone.")
                except Exception as e:
                    logger.error(f"Failed to kill process {pid}: {e}")

        kill_process_on_port(PROXY_PORT)

        uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT, log_level="info")
    finally:
        cleanup()
