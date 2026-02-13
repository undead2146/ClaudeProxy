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
        uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT, log_level="info")
    finally:
        cleanup()
