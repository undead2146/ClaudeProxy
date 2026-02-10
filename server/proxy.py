#!/usr/bin/env python3
"""
Claude Code Proxy - Unified Router for Z.AI and Antigravity (Gemini)
"""

import os
import sys
import json
import logging
import hashlib
import asyncio
import subprocess
import threading
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime

import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse, Response, HTMLResponse
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

# Authentication Configuration
# If PROXY_API_KEY is set, all requests (except health check) require this key
# The key can be passed via:
# 1. x-api-key header (Standard Anthropic client)
# 2. Authorization header (Bearer <key>)
# 3. x-proxy-key header
# 4. ?key=<key> query parameter (for dashboard/browser access)
PROXY_API_KEY = os.getenv("PROXY_API_KEY")

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check and favicon
        if request.url.path in ["/health", "/favicon.ico"]:
            return await call_next(request)

        # If no key is configured, allow all (Legacy/Insecure mode)
        # But we should probably warn about this in logs
        if not PROXY_API_KEY:
            return await call_next(request)

        # Check for key in various locations
        client_key = None

        # 1. Query param (easiest for browser/dashboard)
        if "key" in request.query_params:
            client_key = request.query_params["key"]

        # 2. x-api-key header (Anthropic clients)
        elif "x-api-key" in request.headers:
            client_key = request.headers["x-api-key"]

        # 3. Authorization header
        elif "authorization" in request.headers:
            auth = request.headers["authorization"]
            if auth.lower().startswith("bearer "):
                client_key = auth.split(" ", 1)[1]
            else:
                client_key = auth

        # 4. Custom header
        elif "x-proxy-key" in request.headers:
            client_key = request.headers["x-proxy-key"]

        # Validate
        if client_key == PROXY_API_KEY:
            return await call_next(request)
        else:
            return JSONResponse(
                content={
                    "error": {
                        "type": "authentication_error",
                        "message": "Invalid or missing Proxy API Key. Please provide the correct key via x-api-key header or ?key= query parameter."
                    }
                },
                status_code=401
            )

# Configure logging
log_file = os.getenv("CLAUDE_PROXY_LOG_FILE")
logging_config = {
    "level": logging.INFO,
    "format": '%(asctime)s - %(levelname)s - %(message)s',
}

if log_file:
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    logging_config["filename"] = log_file
    logging_config["filemode"] = 'a'
else:
    logging_config["stream"] = sys.stdout

logging.basicConfig(**logging_config)
logger = logging.getLogger(__name__)

# Provider configurations
HAIKU_PROVIDER_API_KEY = os.getenv("HAIKU_PROVIDER_API_KEY")
HAIKU_PROVIDER_BASE_URL = os.getenv("HAIKU_PROVIDER_BASE_URL")
OPUS_PROVIDER_API_KEY = os.getenv("OPUS_PROVIDER_API_KEY")
OPUS_PROVIDER_BASE_URL = os.getenv("OPUS_PROVIDER_BASE_URL")
SONNET_PROVIDER_API_KEY = os.getenv("SONNET_PROVIDER_API_KEY")
SONNET_PROVIDER_BASE_URL = os.getenv("SONNET_PROVIDER_BASE_URL")

# Z.AI Model mappings (when using Z.AI provider)
ZAI_HAIKU_MODEL = os.getenv("ZAI_HAIKU_MODEL", "zai-4.7")
ZAI_SONNET_MODEL = os.getenv("ZAI_SONNET_MODEL", "zai-4.7")
ZAI_OPUS_MODEL = os.getenv("ZAI_OPUS_MODEL", "zai-4.7")

# Antigravity configuration
ANTIGRAVITY_ENABLED = os.getenv("ANTIGRAVITY_ENABLED", "false").lower() == "true"
ANTIGRAVITY_PORT = int(os.getenv("ANTIGRAVITY_PORT", "8081"))
ANTIGRAVITY_BASE_URL = f"http://localhost:{ANTIGRAVITY_PORT}"
ANTIGRAVITY_CONFIG_DIR = os.getenv("ANTIGRAVITY_CONFIG_DIR", ".antigravity")

# Runtime configuration file
CONFIG_FILE = Path("config.json")

# Favorites storage file
FAVORITES_FILE = Path("favorites.json")

# Configuration lock for thread-safe updates
config_lock = threading.Lock()
favorites_lock = threading.Lock()

# Configuration lock for thread-safe updates
config_lock = threading.Lock()

# Runtime configuration (loaded from file or env vars)
runtime_config = {
    "sonnet_provider": os.getenv("SONNET_PROVIDER", "antigravity"),
    "haiku_provider": os.getenv("HAIKU_PROVIDER", "antigravity"),
    "opus_provider": os.getenv("OPUS_PROVIDER", "anthropic"),
    "sonnet_model": os.getenv("ANTIGRAVITY_SONNET_MODEL", "gemini-3-pro-high"),
    "haiku_model": os.getenv("ANTIGRAVITY_HAIKU_MODEL", "gemini-3-flash"),
    "opus_model": os.getenv("ANTIGRAVITY_OPUS_MODEL", "gemini-3-pro-high"),
    "last_updated": datetime.now().isoformat()
}

# In-memory log buffer (last 100 log entries)
from collections import deque
log_buffer = deque(maxlen=100)
log_buffer_lock = threading.Lock()

# Import token tracker
from token_tracker import TokenUsageTracker
token_tracker = TokenUsageTracker()

# OAuth refresh lock to prevent concurrent refresh attempts
oauth_refresh_lock = threading.Lock()

# Custom handler to capture logs in memory
class BufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": self.format(record)
        }
        with log_buffer_lock:
            log_buffer.append(log_entry)

# Add buffer handler to logger
buffer_handler = BufferHandler()
buffer_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
logger.addHandler(buffer_handler)

# Provider routing configuration (which provider to use for each tier)
# These are now dynamic and read from runtime_config
def get_sonnet_provider():
    with config_lock:
        return runtime_config.get("sonnet_provider", "antigravity")

def get_haiku_provider():
    with config_lock:
        return runtime_config.get("haiku_provider", "antigravity")

def get_opus_provider():
    with config_lock:
        return runtime_config.get("opus_provider", "anthropic")

SONNET_PROVIDER = os.getenv("SONNET_PROVIDER", "antigravity")
HAIKU_PROVIDER = os.getenv("HAIKU_PROVIDER", "antigravity")
OPUS_PROVIDER = os.getenv("OPUS_PROVIDER", "anthropic")

# Antigravity/Gemini model mappings (when using Antigravity provider)
ANTIGRAVITY_SONNET_MODEL = os.getenv("ANTIGRAVITY_SONNET_MODEL", "gemini-3-pro-high")
ANTIGRAVITY_HAIKU_MODEL = os.getenv("ANTIGRAVITY_HAIKU_MODEL", "gemini-3-flash")
ANTIGRAVITY_OPUS_MODEL = os.getenv("ANTIGRAVITY_OPUS_MODEL", "gemini-3-pro-high")

# GitHub Copilot configuration (via copilot-api proxy)
ENABLE_COPILOT = os.getenv("ENABLE_COPILOT", "false").lower() == "true"
GITHUB_COPILOT_BASE_URL = os.getenv("GITHUB_COPILOT_BASE_URL", "http://localhost:4141")
GITHUB_COPILOT_SONNET_MODEL = os.getenv("GITHUB_COPILOT_SONNET_MODEL", "claude-sonnet-4.5")
GITHUB_COPILOT_HAIKU_MODEL = os.getenv("GITHUB_COPILOT_HAIKU_MODEL", "claude-haiku-4.5")
GITHUB_COPILOT_OPUS_MODEL = os.getenv("GITHUB_COPILOT_OPUS_MODEL", "claude-opus-4.5")

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api")
OPENROUTER_SONNET_MODEL = os.getenv("OPENROUTER_SONNET_MODEL", "anthropic/claude-sonnet-4.5")
OPENROUTER_HAIKU_MODEL = os.getenv("OPENROUTER_HAIKU_MODEL", "anthropic/claude-haiku-4.5")
OPENROUTER_OPUS_MODEL = os.getenv("OPENROUTER_OPUS_MODEL", "anthropic/claude-opus-4.5")

# Custom provider configuration - for any Anthropic-compatible API
CUSTOM_PROVIDER_API_KEY = os.getenv("CUSTOM_PROVIDER_API_KEY")
CUSTOM_PROVIDER_BASE_URL = os.getenv("CUSTOM_PROVIDER_BASE_URL")
CUSTOM_PROVIDER_SONNET_MODEL = os.getenv("CUSTOM_PROVIDER_SONNET_MODEL", "claude-sonnet-4.5")
CUSTOM_PROVIDER_HAIKU_MODEL = os.getenv("CUSTOM_PROVIDER_HAIKU_MODEL", "claude-haiku-4.5")
CUSTOM_PROVIDER_OPUS_MODEL = os.getenv("CUSTOM_PROVIDER_OPUS_MODEL", "claude-opus-4.5")

# Anthropic (OAuth) Default Model Mappings
ANTHROPIC_SONNET_MODEL = os.getenv("ANTHROPIC_SONNET_MODEL", "claude-sonnet-4-5-20250929")
ANTHROPIC_HAIKU_MODEL = os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-3-5-haiku-20241022")
ANTHROPIC_OPUS_MODEL = os.getenv("ANTHROPIC_OPUS_MODEL", "claude-opus-4-20250514")

ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8082"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))

# Antigravity process handle
antigravity_process = None

# OAuth refresh rate limiting to prevent retry loops
_last_oauth_refresh_failure = 0
_OAUTH_REFRESH_COOLDOWN = 60  # seconds - wait before retrying failed refresh


def build_custom_provider_models() -> list:
    """Build the custom provider models list from environment variables."""
    models = []

    # Read directly from environment to get latest values
    sonnet_model = os.getenv("CUSTOM_PROVIDER_SONNET_MODEL", "claude-sonnet-4.5")
    haiku_model = os.getenv("CUSTOM_PROVIDER_HAIKU_MODEL", "claude-haiku-4.5")
    opus_model = os.getenv("CUSTOM_PROVIDER_OPUS_MODEL", "claude-opus-4.5")

    # Add configured models if they have values
    if sonnet_model:
        models.append(sonnet_model)
    if haiku_model:
        models.append(haiku_model)
    if opus_model:
        models.append(opus_model)

    # Deduplicate while preserving order
    seen = set()
    unique_models = []
    for model in models:
        if model not in seen:
            seen.add(model)
            unique_models.append(model)

    return unique_models


def get_oauth_token():
    """Read OAuth token from Claude Code's credentials file, refreshing if needed."""
    global _last_oauth_refresh_failure
    try:
        creds_path = Path.home() / ".claude" / ".credentials.json"
        if not creds_path.exists():
            return None

        with open(creds_path, 'r') as f:
            creds = json.load(f)

        oauth_data = creds.get("claudeAiOauth", {})
        access_token = oauth_data.get("accessToken")
        refresh_token = oauth_data.get("refreshToken")
        expires_at = oauth_data.get("expiresAt", 0)

        # Check if token is expired or will expire in the next 5 minutes
        current_time_ms = int(datetime.now().timestamp() * 1000)
        buffer_ms = 5 * 60 * 1000  # 5 minutes buffer

        if expires_at and (current_time_ms + buffer_ms) >= expires_at:
            logger.info("[OAuth] Access token expired or expiring soon, refreshing...")

            # Refresh the token
            if not refresh_token:
                logger.error("[OAuth] No refresh token available")
                return None

            # Use lock to prevent concurrent refresh attempts
            # Multiple requests might trigger refresh simultaneously, but refresh tokens
            # can only be used once, so we need to serialize the refresh attempts
            with oauth_refresh_lock:
                # Re-read credentials after acquiring lock - another thread may have already refreshed
                with open(creds_path, 'r') as f:
                    creds = json.load(f)
                oauth_data = creds.get("claudeAiOauth", {})
                access_token = oauth_data.get("accessToken")
                refresh_token = oauth_data.get("refreshToken")
                expires_at = oauth_data.get("expiresAt", 0)

                # Check if still expired (another thread may have refreshed)
                current_time_ms = int(datetime.now().timestamp() * 1000)
                current_time_sec = int(datetime.now().timestamp())
                if not expires_at or (current_time_ms + buffer_ms) < expires_at:
                    logger.info("[OAuth] Token was already refreshed by another thread")
                    return oauth_data.get("accessToken")

                # Check if we're in cooldown after a failed refresh
                if current_time_sec - _last_oauth_refresh_failure < _OAUTH_REFRESH_COOLDOWN:
                    logger.warning(f"[OAuth] Refresh in cooldown (failed {(current_time_sec - _last_oauth_refresh_failure)}s ago), using stale token if available")
                    # Return the expired token anyway - better than nothing
                    return oauth_data.get("accessToken")

                try:
                    import httpx
                    # Anthropic's OAuth endpoint expects JSON, not form-encoded data
                    refresh_response = httpx.post(
                        "https://api.anthropic.com/v1/oauth/token",
                        json={
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token
                        },
                        headers={
                            "Content-Type": "application/json",
                            "anthropic-version": "2023-06-01"
                        },
                        timeout=10.0
                    )

                    if refresh_response.status_code == 200:
                        new_token_data = refresh_response.json()

                        # Update credentials with new token
                        oauth_data["accessToken"] = new_token_data.get("access_token")
                        oauth_data["expiresAt"] = current_time_ms + (new_token_data.get("expires_in", 3600) * 1000)

                        # If a new refresh token is provided, update it too
                        if "refresh_token" in new_token_data:
                            oauth_data["refreshToken"] = new_token_data["refresh_token"]

                        # Save updated credentials
                        creds["claudeAiOauth"] = oauth_data
                        with open(creds_path, 'w') as f:
                            json.dump(creds, f, indent=2)

                        logger.info("[OAuth] Token refreshed successfully")
                        _last_oauth_refresh_failure = 0  # Reset on success
                        return oauth_data["accessToken"]
                    else:
                        _last_oauth_refresh_failure = int(datetime.now().timestamp())
                        logger.error(f"[OAuth] Token refresh failed: {refresh_response.status_code} - {refresh_response.text[:200]}")
                        return None

                except Exception as refresh_error:
                    _last_oauth_refresh_failure = int(datetime.now().timestamp())
                    logger.error(f"[OAuth] Token refresh error: {refresh_error}")
                    return None

        return access_token

    except Exception as e:
        logger.error(f"[OAuth] Failed to read credentials: {e}")
        return None


def has_oauth_credentials() -> bool:
    """Check if OAuth credentials file exists without triggering token refresh."""
    try:
        creds_path = Path.home() / ".claude" / ".credentials.json"
        if not creds_path.exists():
            return False
        with open(creds_path, 'r') as f:
            creds = json.load(f)
        oauth_data = creds.get("claudeAiOauth", {})
        return bool(oauth_data.get("accessToken"))
    except Exception:
        return False


def get_provider_config(model: str) -> Tuple[Optional[str], Optional[str], str, str, str]:
    """Determine which provider to use based on model name.

    Returns: (api_key, base_url, tier, translated_model, provider_type)
    provider_type can be: 'glm', 'antigravity', 'anthropic', or 'unknown'
    """
    # Detect tier from model name
    tier = "Unknown"
    model_lower = model.lower()

    # First, check if model matches any configured model names
    if ZAI_HAIKU_MODEL and model == ZAI_HAIKU_MODEL:
        tier = "Haiku"
    elif ZAI_SONNET_MODEL and model == ZAI_SONNET_MODEL:
        tier = "Sonnet"
    elif ZAI_OPUS_MODEL and model == ZAI_OPUS_MODEL:
        tier = "Opus"
    elif ANTIGRAVITY_HAIKU_MODEL and model == ANTIGRAVITY_HAIKU_MODEL:
        tier = "Haiku"
    elif ANTIGRAVITY_SONNET_MODEL and model == ANTIGRAVITY_SONNET_MODEL:
        tier = "Sonnet"
    elif ANTIGRAVITY_OPUS_MODEL and model == ANTIGRAVITY_OPUS_MODEL:
        tier = "Opus"
    # Then check for tier keywords in model name
    elif "haiku" in model_lower:
        tier = "Haiku"
    elif "sonnet" in model_lower:
        tier = "Sonnet"
    elif "opus" in model_lower:
        tier = "Opus"
    # Check for Z.AI model patterns
    elif model_lower.startswith("glm-") or model_lower.startswith("zai-"):
        # Infer tier from version number
        if "4.7" in model_lower or "flash" in model_lower:
            tier = "Haiku"
        else:
            tier = "Sonnet"
    # Check for Gemini model patterns
    elif model_lower.startswith("gemini-"):
        if "flash" in model_lower:
            tier = "Haiku"
        else:
            tier = "Sonnet"

    # Get current provider configuration (thread-safe)
    current_sonnet_provider = get_sonnet_provider()
    current_haiku_provider = get_haiku_provider()
    current_opus_provider = get_opus_provider()

    # Get selected models from runtime config
    with config_lock:
        sonnet_model = runtime_config.get("sonnet_model", ANTIGRAVITY_SONNET_MODEL)
        haiku_model = runtime_config.get("haiku_model", ANTIGRAVITY_HAIKU_MODEL)
        opus_model = runtime_config.get("opus_model", ANTIGRAVITY_OPUS_MODEL)

    # Route based on configured provider for this tier
    if tier == "Sonnet":
        if current_sonnet_provider == "antigravity" and ANTIGRAVITY_ENABLED:
            logger.info(f"[Proxy] Routing Sonnet  Antigravity ({sonnet_model})")
            return None, ANTIGRAVITY_BASE_URL, tier, sonnet_model, "antigravity"
        elif current_sonnet_provider in ["glm", "zai"] and ZAI_SONNET_MODEL and SONNET_PROVIDER_BASE_URL:
            logger.info(f"[Proxy] Routing Sonnet  Z.AI ({ZAI_SONNET_MODEL})")
            return SONNET_PROVIDER_API_KEY, SONNET_PROVIDER_BASE_URL, tier, ZAI_SONNET_MODEL, "zai"
        elif current_sonnet_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Sonnet  GitHub Copilot ({sonnet_model})")
            return None, GITHUB_COPILOT_BASE_URL, tier, sonnet_model, "copilot"
        elif current_sonnet_provider == "openrouter" and OPENROUTER_API_KEY:
            logger.info(f"[Proxy] Routing Sonnet  OpenRouter ({OPENROUTER_SONNET_MODEL})")
            return OPENROUTER_API_KEY, OPENROUTER_BASE_URL, tier, OPENROUTER_SONNET_MODEL, "openrouter"
        elif current_sonnet_provider == "custom":
            # Read directly from environment to get latest values
            custom_api_key = os.getenv("CUSTOM_PROVIDER_API_KEY")
            custom_base_url = os.getenv("CUSTOM_PROVIDER_BASE_URL")
            custom_sonnet_model = os.getenv("CUSTOM_PROVIDER_SONNET_MODEL", "claude-sonnet-4.5")
            if custom_api_key and custom_base_url:
                logger.info(f"[Proxy] Routing Sonnet  Custom Provider ({custom_sonnet_model})")
                return custom_api_key, custom_base_url, tier, custom_sonnet_model, "custom"
        else:
            logger.info(f"[Proxy] Routing Sonnet  Anthropic (OAuth)")
            # For Anthropic, always use a real Claude model name (translate short names to full IDs)
            return None, None, tier, ANTHROPIC_SONNET_MODEL, "anthropic"

    elif tier == "Haiku":
        if current_haiku_provider == "antigravity" and ANTIGRAVITY_ENABLED:
            logger.info(f"[Proxy] Routing Haiku  Antigravity ({haiku_model})")
            return None, ANTIGRAVITY_BASE_URL, tier, haiku_model, "antigravity"
        elif current_haiku_provider in ["glm", "zai"] and ZAI_HAIKU_MODEL and HAIKU_PROVIDER_BASE_URL:
            logger.info(f"[Proxy] Routing Haiku  Z.AI ({ZAI_HAIKU_MODEL})")
            return HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL, tier, ZAI_HAIKU_MODEL, "zai"
        elif current_haiku_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Haiku  GitHub Copilot ({haiku_model})")
            return None, GITHUB_COPILOT_BASE_URL, tier, haiku_model, "copilot"
        elif current_haiku_provider == "openrouter" and OPENROUTER_API_KEY:
            logger.info(f"[Proxy] Routing Haiku  OpenRouter ({OPENROUTER_HAIKU_MODEL})")
            return OPENROUTER_API_KEY, OPENROUTER_BASE_URL, tier, OPENROUTER_HAIKU_MODEL, "openrouter"
        elif current_haiku_provider == "custom":
            # Read directly from environment to get latest values
            custom_api_key = os.getenv("CUSTOM_PROVIDER_API_KEY")
            custom_base_url = os.getenv("CUSTOM_PROVIDER_BASE_URL")
            custom_haiku_model = os.getenv("CUSTOM_PROVIDER_HAIKU_MODEL", "claude-haiku-4.5")
            if custom_api_key and custom_base_url:
                logger.info(f"[Proxy] Routing Haiku  Custom Provider ({custom_haiku_model})")
                return custom_api_key, custom_base_url, tier, custom_haiku_model, "custom"
        else:
            logger.info(f"[Proxy] Routing Haiku  Anthropic (OAuth)")
            # For Anthropic, always use a real Claude model name (translate short names to full IDs)
            return None, None, tier, ANTHROPIC_HAIKU_MODEL, "anthropic"

    elif tier == "Opus":
        if current_opus_provider == "antigravity" and ANTIGRAVITY_ENABLED:
            logger.info(f"[Proxy] Routing Opus  Antigravity ({opus_model})")
            return None, ANTIGRAVITY_BASE_URL, tier, opus_model, "antigravity"
        elif current_opus_provider in ["glm", "zai"] and ZAI_OPUS_MODEL and OPUS_PROVIDER_BASE_URL:
            logger.info(f"[Proxy] Routing Opus  Z.AI ({ZAI_OPUS_MODEL})")
            return OPUS_PROVIDER_API_KEY, OPUS_PROVIDER_BASE_URL, tier, ZAI_OPUS_MODEL, "zai"
        elif current_opus_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Opus ? GitHub Copilot ({GITHUB_COPILOT_OPUS_MODEL})")
            return None, GITHUB_COPILOT_BASE_URL, tier, GITHUB_COPILOT_OPUS_MODEL, "copilot"
        elif current_opus_provider == "openrouter" and OPENROUTER_API_KEY:
            logger.info(f"[Proxy] Routing Opus  OpenRouter ({OPENROUTER_OPUS_MODEL})")
            return OPENROUTER_API_KEY, OPENROUTER_BASE_URL, tier, OPENROUTER_OPUS_MODEL, "openrouter"
        elif current_opus_provider == "custom":
            # Read directly from environment to get latest values
            custom_api_key = os.getenv("CUSTOM_PROVIDER_API_KEY")
            custom_base_url = os.getenv("CUSTOM_PROVIDER_BASE_URL")
            custom_opus_model = os.getenv("CUSTOM_PROVIDER_OPUS_MODEL", "claude-opus-4.5")
            if custom_api_key and custom_base_url:
                logger.info(f"[Proxy] Routing Opus  Custom Provider ({custom_opus_model})")
                return custom_api_key, custom_base_url, tier, custom_opus_model, "custom"
        else:
            logger.info(f"[Proxy] Routing Opus  Anthropic (OAuth)")
            # For Anthropic, always use a real Claude model name (translate short names to full IDs)
            return None, None, tier, ANTHROPIC_OPUS_MODEL, "anthropic"

    # Unknown model - try to infer or default to Anthropic
    logger.warning(f"[Proxy] Unknown model tier for '{model}', defaulting to Haiku tier")
    # Default to Haiku routing
    current_haiku_provider = get_haiku_provider()
    if current_haiku_provider == "antigravity" and ANTIGRAVITY_ENABLED:
        return None, ANTIGRAVITY_BASE_URL, "Haiku", ANTIGRAVITY_HAIKU_MODEL, "antigravity"
    elif current_haiku_provider in ["glm", "zai"] and ZAI_HAIKU_MODEL and HAIKU_PROVIDER_BASE_URL:
        return HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL, "Haiku", ZAI_HAIKU_MODEL, "zai"
    elif current_haiku_provider == "copilot" and ENABLE_COPILOT:
        return None, GITHUB_COPILOT_BASE_URL, "Haiku", haiku_model, "copilot"
    else:
        return None, None, "Unknown", ANTHROPIC_HAIKU_MODEL, "anthropic"

def generate_signature(thinking_content: str) -> str:
    """Generate a valid signature for thinking block."""
    # Create a hash of the thinking content
    return hashlib.sha256(thinking_content.encode()).hexdigest()[:32]

def fix_thinking_blocks(body_json: dict, has_thinking_beta: bool, use_real_anthropic: bool = False) -> dict:
    """
    Strip thinking blocks from messages when sending to Anthropic.
    Anthropic's API doesn't accept thinking blocks with signatures.
    """
    if not use_real_anthropic:
        return body_json

    # Remove thinking blocks from messages
    if 'messages' in body_json:
        for message in body_json['messages']:
            if isinstance(message.get('content'), list):
                # Filter out thinking content blocks
                message['content'] = [
                    block for block in message['content']
                    if block.get('type') != 'thinking'
                ]

    return body_json

def has_thinking_in_beta(beta_header: str) -> bool:
    """Check if thinking is enabled in beta features."""
    if not beta_header:
        return False

    thinking_keywords = ['thinking', 'extended-thinking', 'interleaved-thinking']
    features_lower = beta_header.lower()

    return any(keyword in features_lower for keyword in thinking_keywords)


async def proxy_to_antigravity(body_json: dict, original_headers: dict, endpoint: str) -> JSONResponse | StreamingResponse:
    """Proxy request to Antigravity server."""
    try:
        target_url = f"{ANTIGRAVITY_BASE_URL}/v1/{endpoint}"
        target_headers = {
            "Content-Type": "application/json",
            "x-api-key": "test",
            "anthropic-version": "2023-06-01"
        }

        # Log the exact request being sent
        logger.info(f"[Antigravity] Sending to {target_url}")
        logger.info(f"[Antigravity] Model in body: {body_json.get('model')}")
        logger.info(f"[Antigravity] Stream: {body_json.get('stream', False)}")
        logger.info(f"[Antigravity] Max tokens: {body_json.get('max_tokens', 'not set')}")
        logger.info(f"[Antigravity] Messages count: {len(body_json.get('messages', []))}")

        # Log first message preview for debugging
        messages = body_json.get('messages', [])
        if messages:
            first_msg = messages[0]
            content_preview = str(first_msg.get('content', ''))[:100]
            logger.info(f"[Antigravity] First message role: {first_msg.get('role')}, content preview: {content_preview}")

        # Forward beta features header BUT strip thinking features (Gemini doesn't support them)
        if "anthropic-beta" in original_headers:
            beta_header = original_headers["anthropic-beta"]
            # Remove thinking-related features
            beta_parts = [part.strip() for part in beta_header.split(',')]
            filtered_parts = [part for part in beta_parts if 'thinking' not in part.lower()]

            if filtered_parts:
                target_headers["anthropic-beta"] = ','.join(filtered_parts)
                logger.info(f"[Antigravity] Beta header (filtered): {target_headers['anthropic-beta']}")
            else:
                logger.info(f"[Antigravity] All beta features filtered out (thinking not supported)")

        # Also strip thinking from messages
        if 'messages' in body_json:
            for message in body_json['messages']:
                if isinstance(message.get('content'), list):
                    # Remove thinking content blocks
                    message['content'] = [
                        block for block in message['content']
                        if block.get('type') != 'thinking'
                    ]

        request_body = json.dumps(body_json).encode('utf-8')

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            stream = body_json.get("stream", False)

            if stream:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Antigravity] Response status: {response.status_code}")

                if response.status_code >= 400:
                    error_text = response.text[:500]
                    logger.error(f"[Antigravity] Error response: {error_text}")

                async def stream_response():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    stream_response(),
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    media_type="text/event-stream",
                )
            else:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Antigravity] Response status: {response.status_code}")

                if response.status_code >= 400:
                    error_text = response.text[:500]
                    logger.error(f"[Antigravity] Error response: {error_text}")
                else:
                    # Track token usage for successful responses
                    try:
                        response_data = response.json()
                        usage = response_data.get("usage", {})
                        if usage:
                            token_tracker.record_usage(
                                input_tokens=usage.get("input_tokens", 0),
                                output_tokens=usage.get("output_tokens", 0),
                                provider="antigravity",
                                model=body_json.get("model", "unknown"),
                                tier="unknown"
                            )
                    except Exception as e:
                        logger.warning(f"[TokenTracker] Failed to record usage: {e}")

                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                )
    except httpx.ReadTimeout as e:
        logger.error(f"[Antigravity] ReadTimeout after {REQUEST_TIMEOUT}s - Google account may be rate-limited or expired. Try: npx antigravity-claude-proxy@latest accounts add")
        return JSONResponse(content={
            "error": "Antigravity server timeout - your Google accounts may be rate-limited or expired",
            "suggestion": "Run: npx antigravity-claude-proxy@latest accounts add"
        }, status_code=504)
    except Exception as e:
        logger.error(f"[Antigravity] Error: {type(e).__name__}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def proxy_to_copilot(body_json: dict, original_headers: dict, endpoint: str) -> JSONResponse | StreamingResponse:
    """Proxy request to GitHub Copilot API."""
    try:
        target_url = f"{GITHUB_COPILOT_BASE_URL}/v1/{endpoint}"
        target_headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer dummy"  # copilot-api handles auth internally
        }

        # Copy Anthropic headers
        for header in ["anthropic-version", "anthropic-beta"]:
            if header in original_headers:
                target_headers[header] = original_headers[header]

        logger.info(f"[Copilot] Sending to {target_url}")
        logger.info(f"[Copilot] Model: {body_json.get('model')}")

        request_body = json.dumps(body_json).encode('utf-8')

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            stream = body_json.get("stream", False)

            if stream:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Copilot] Response status: {response.status_code}")

                async def stream_response():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    stream_response(),
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    media_type="text/event-stream",
                )
            else:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Copilot] Response status: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"[Copilot] Error: {response.text[:500]}")
                    return JSONResponse(
                        content=response.json(),
                        status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    )

                # Track token usage for successful responses
                try:
                    response_data = response.json()
                    usage = response_data.get("usage", {})
                    if usage:
                        token_tracker.record_usage(
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                            provider="copilot",
                            model=body_json.get("model", "unknown"),
                            tier="unknown"
                        )
                except Exception as e:
                    logger.warning(f"[TokenTracker] Failed to record usage: {e}")

                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                )

    except httpx.TimeoutException:
        logger.error(f"[Copilot] Timeout after {REQUEST_TIMEOUT}s")
        return JSONResponse(content={
            "error": "GitHub Copilot API timeout"
        }, status_code=504)
    except Exception as e:
        logger.error(f"[Copilot] Error: {type(e).__name__}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def proxy_to_openrouter(body_json: dict, original_headers: dict, endpoint: str) -> JSONResponse | StreamingResponse:
    """Proxy request to OpenRouter API."""
    try:
        target_url = f"{OPENROUTER_BASE_URL}/v1/{endpoint}"
        target_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://claude-code-proxy.local",
            "X-Title": "Claude Code Proxy"
        }

        # Copy Anthropic headers that OpenRouter supports
        for header in ["anthropic-version", "anthropic-beta"]:
            if header in original_headers:
                target_headers[header] = original_headers[header]

        logger.info(f"[OpenRouter] Sending to {target_url}")
        logger.info(f"[OpenRouter] Model: {body_json.get('model')}")

        request_body = json.dumps(body_json).encode('utf-8')

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            stream = body_json.get("stream", False)

            if stream:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[OpenRouter] Response status: {response.status_code}")

                async def stream_response():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                # Filter headers that should not be forwarded
                # httpx already decompressed the response, so remove content-encoding
                filtered_headers = {k: v for k, v in response.headers.items()
                                    if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']}

                return StreamingResponse(
                    stream_response(),
                    status_code=response.status_code,
                    headers=filtered_headers,
                    media_type="text/event-stream",
                )
            else:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[OpenRouter] Response status: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"[OpenRouter] Error: {response.text[:500]}")
                    return JSONResponse(
                        content=response.json(),
                        status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    )

                # Track token usage for successful responses
                try:
                    response_data = response.json()
                    usage = response_data.get("usage", {})
                    if usage:
                        token_tracker.record_usage(
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                            provider="openrouter",
                            model=body_json.get("model", "unknown"),
                            tier="unknown"
                        )
                except Exception as e:
                    logger.warning(f"[TokenTracker] Failed to record usage: {e}")

                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                )

    except httpx.TimeoutException:
        logger.error(f"[OpenRouter] Timeout after {REQUEST_TIMEOUT}s")
        return JSONResponse(content={
            "error": "OpenRouter API timeout"
        }, status_code=504)
    except Exception as e:
        logger.error(f"[OpenRouter] Error: {type(e).__name__}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def proxy_to_custom(body_json: dict, original_headers: dict, endpoint: str) -> JSONResponse | StreamingResponse:
    """Proxy request to custom Anthropic-compatible API."""
    try:
        # Check if base URL already includes /v1 or if we should skip it
        base_url = CUSTOM_PROVIDER_BASE_URL.rstrip('/') if CUSTOM_PROVIDER_BASE_URL else ""
        skip_v1 = os.getenv("CUSTOM_PROVIDER_SKIP_V1", "false").lower() == "true"

        if skip_v1:
            target_url = f"{base_url}/{endpoint}"
        else:
            target_url = f"{base_url}/v1/{endpoint}"

        target_headers = {
            "Content-Type": "application/json",
            "x-api-key": CUSTOM_PROVIDER_API_KEY,
        }

        # Copy Anthropic headers
        for header in ["anthropic-version", "anthropic-beta"]:
            if header in original_headers:
                target_headers[header] = original_headers[header]

        logger.info(f"[Custom] Sending to {target_url}")
        logger.info(f"[Custom] Model: {body_json.get('model')}")

        request_body = json.dumps(body_json).encode('utf-8')

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            stream = body_json.get("stream", False)

            if stream:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Custom] Response status: {response.status_code}")

                async def stream_response():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                filtered_headers = {k: v for k, v in response.headers.items()
                                    if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']}

                return StreamingResponse(
                    stream_response(),
                    status_code=response.status_code,
                    headers=filtered_headers,
                    media_type="text/event-stream",
                )
            else:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Custom] Response status: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"[Custom] Error: {response.text[:500]}")
                    return JSONResponse(
                        content=response.json(),
                        status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    )

                # Track token usage for successful responses
                try:
                    response_data = response.json()
                    usage = response_data.get("usage", {})
                    if usage:
                        token_tracker.record_usage(
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                            provider="custom",
                            model=body_json.get("model", "unknown"),
                            tier="unknown"
                        )
                except Exception as e:
                    logger.warning(f"[TokenTracker] Failed to record usage: {e}")

                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                )

    except httpx.TimeoutException:
        logger.error(f"[Custom] Timeout after {REQUEST_TIMEOUT}s")
        return JSONResponse(content={
            "error": "Custom provider API timeout"
        }, status_code=504)
    except Exception as e:
        logger.error(f"[Custom] Error: {type(e).__name__}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


def convert_anthropic_to_openai(anthropic_body: dict) -> dict:
    """Convert Anthropic API request format to OpenAI format."""
    openai_body = {
        "model": anthropic_body.get("model"),
        "messages": [],
        "stream": anthropic_body.get("stream", False),
    }

    # Add optional parameters
    if "max_tokens" in anthropic_body:
        openai_body["max_tokens"] = anthropic_body["max_tokens"]
    if "temperature" in anthropic_body:
        openai_body["temperature"] = anthropic_body["temperature"]
    if "top_p" in anthropic_body:
        openai_body["top_p"] = anthropic_body["top_p"]
    if "stop_sequences" in anthropic_body:
        openai_body["stop"] = anthropic_body["stop_sequences"]

    # Convert tools if present
    if "tools" in anthropic_body:
        openai_body["tools"] = []
        for tool in anthropic_body["tools"]:
            openai_body["tools"].append({
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {})
                }
            })
        logger.info(f"[Convert] Converted {len(openai_body['tools'])} tools to OpenAI format")

    # Convert system message
    if "system" in anthropic_body:
        if isinstance(anthropic_body["system"], str):
            openai_body["messages"].append({
                "role": "system",
                "content": anthropic_body["system"]
            })
        elif isinstance(anthropic_body["system"], list):
            # Handle system message blocks
            system_content = ""
            for block in anthropic_body["system"]:
                if block.get("type") == "text":
                    system_content += block.get("text", "")
            if system_content:
                openai_body["messages"].append({
                    "role": "system",
                    "content": system_content
                })

    # Convert messages
    for msg in anthropic_body.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")

        if isinstance(content, str):
            openai_body["messages"].append({
                "role": role,
                "content": content
            })
        elif isinstance(content, list):
            # Handle content blocks
            openai_content = []
            tool_calls = []
            has_tool_results = False

            for block in content:
                if block.get("type") == "text":
                    openai_content.append({
                        "type": "text",
                        "text": block.get("text", "")
                    })
                elif block.get("type") == "image":
                    # Convert image format
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        openai_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{source.get('media_type', 'image/png')};base64,{source.get('data', '')}"
                            }
                        })
                elif block.get("type") == "tool_use":
                    # Convert Anthropic tool_use to OpenAI tool_calls
                    tool_calls.append({
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    })
                elif block.get("type") == "tool_result":
                    # Convert Anthropic tool_result to OpenAI tool message
                    has_tool_results = True
                    # Tool results need to be separate messages in OpenAI format
                    content = block.get("content")

                    # Handle content that might be a list of blocks
                    if isinstance(content, list):
                        # Extract text from content blocks
                        text_parts = []
                        for content_block in content:
                            if isinstance(content_block, dict) and content_block.get("type") == "text":
                                text_parts.append(content_block.get("text", ""))
                        content = "\n".join(text_parts) if text_parts else json.dumps(content)
                    elif not isinstance(content, str):
                        content = json.dumps(content)

                    # Preserve error information - if is_error is true, prepend ERROR marker
                    if block.get("is_error"):
                        content = f"ERROR: {content}"

                    openai_body["messages"].append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": content
                    })

            # Don't add message if it only contained tool_results (already added above)
            if not has_tool_results:
                msg_dict = {
                    "role": role,
                    "content": openai_content if len(openai_content) > 1 else (openai_content[0]["text"] if openai_content else "")
                }

                # Add tool_calls if present (for assistant messages)
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls

                openai_body["messages"].append(msg_dict)

    return openai_body


def convert_openai_to_anthropic(openai_response: dict) -> dict:
    """Convert OpenAI API response format to Anthropic format."""
    choice = openai_response.get("choices", [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason")

    # Map OpenAI finish reasons to Anthropic stop reasons
    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
        "function_call": "tool_use"
    }

    anthropic_response = {
        "id": openai_response.get("id", ""),
        "type": "message",
        "role": "assistant",
        "content": [],
        "model": openai_response.get("model", ""),
        "stop_reason": stop_reason_map.get(finish_reason, finish_reason or "end_turn"),
        "usage": {
            "input_tokens": openai_response.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": openai_response.get("usage", {}).get("completion_tokens", 0)
        }
    }

    # Convert content
    content = message.get("content", "")
    if content:
        anthropic_response["content"].append({
            "type": "text",
            "text": content
        })

    # Convert tool calls from OpenAI format to Anthropic format
    tool_calls = message.get("tool_calls", [])
    if tool_calls:
        for tool_call in tool_calls:
            if tool_call.get("type") == "function":
                function = tool_call.get("function", {})
                try:
                    # Parse the arguments JSON string
                    arguments = json.loads(function.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}

                anthropic_response["content"].append({
                    "type": "tool_use",
                    "id": tool_call.get("id"),
                    "name": function.get("name"),
                    "input": arguments
                })

    return anthropic_response


def convert_openai_stream_to_anthropic(chunk: bytes) -> bytes:
    """Convert OpenAI streaming format to Anthropic streaming format."""
    # This is a simplified conversion - in production you'd need more robust parsing
    # For now, pass through as-is since both use SSE format
    return chunk


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
            "npx",  # Try PATH first
            "npx.cmd",  # Windows explicit
            r"C:\Program Files\nodejs\npx.cmd",  # Common Windows install
            os.path.expanduser(r"~\AppData\Roaming\npm\npx.cmd"),  # User install
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

        # Check if Node.js is available
        node_check = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if node_check.returncode != 0:
            logger.error("[Antigravity] Node.js not found. Please install Node.js to use Antigravity.")
            return

        logger.info(f"[Antigravity] Node.js version: {node_check.stdout.strip()}")

        # Skip package check - npx will install if needed
        # The --help check can hang on slow networks or with npm cache issues
        logger.info("[Antigravity] Skipping package version check...")

        # Start Antigravity server
        logger.info(f"[Antigravity] Starting server on port {ANTIGRAVITY_PORT}...")

        env = os.environ.copy()
        env["PORT"] = str(ANTIGRAVITY_PORT)

        # Start Antigravity in detached process
        import time
        if os.name == 'nt':
            # Windows: Start in new console without blocking
            antigravity_process = subprocess.Popen(
                [npx_cmd, "antigravity-claude-proxy@latest", "start"],
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Unix: Standard detached process
            antigravity_process = subprocess.Popen(
                [npx_cmd, "antigravity-claude-proxy@latest", "start"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

        # Wait for the server to start and verify it's responding
        max_wait = 15  # Wait up to 15 seconds
        wait_interval = 1
        healthy = False

        for attempt in range(max_wait):
            time.sleep(wait_interval)

            # Check if process crashed
            if antigravity_process.poll() is not None:
                logger.error(f"[Antigravity] Process crashed during startup")
                return

            # Check if server is responding
            try:
                import httpx
                response = httpx.get(f"http://localhost:{ANTIGRAVITY_PORT}/health", timeout=2.0)
                if response.status_code == 200:
                    healthy = True
                    break
            except Exception:
                continue  # Keep waiting

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


async def proxy_request(request: Request, endpoint: str) -> JSONResponse | StreamingResponse:
    """Main proxy function with complete thinking block support."""
    try:
        body = await request.body()
        body_json = json.loads(body) if body else {}
        original_model = body_json.get("model", "claude-sonnet-4-5-20250929")

        logger.info(f"[Proxy] Incoming request for model: {original_model}")

        api_key, base_url, tier, translated_model, provider_type = get_provider_config(original_model)

        # Strip [1m] suffix from model name - it's internal notation, not part of actual API model names
        if "[1m]" in translated_model:
            translated_model = translated_model.replace("[1m]", "")
            logger.info(f"[Proxy] Stripped [1m] suffix: {original_model} → {translated_model}")

        # Update the model in the request body with translated name
        body_json["model"] = translated_model

        original_headers = dict(request.headers)
        use_real_anthropic = False  # Track if using Real Anthropic OAuth

        # Route to Antigravity
        if provider_type == "antigravity":
            logger.info(f"[Proxy] {original_model} → Antigravity ({translated_model})")
            return await proxy_to_antigravity(body_json, original_headers, endpoint)

        # Route to GitHub Copilot (via copilot-api proxy)
        elif provider_type == "copilot":
            logger.info(f"[Proxy] {original_model} → GitHub Copilot ({translated_model})")
            return await proxy_to_copilot(body_json, original_headers, endpoint)

        # Route to OpenRouter
        elif provider_type == "openrouter":
            logger.info(f"[Proxy] {original_model} → OpenRouter ({translated_model})")
            return await proxy_to_openrouter(body_json, original_headers, endpoint)

        # Route to Custom provider
        elif provider_type == "custom":
            logger.info(f"[Proxy] {original_model}  Custom Provider ({translated_model})")
            return await proxy_to_custom(body_json, original_headers, endpoint)

        # Route to Z.AI provider
        elif api_key and base_url and provider_type in ["glm", "zai"]:
            # Alternative provider (Z.AI) - pass through as-is
            target_url = f"{base_url.rstrip('/')}/v1/{endpoint}"
            target_headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key
            }

            for header in ["anthropic-version", "anthropic-beta"]:
                if header in original_headers:
                    target_headers[header] = original_headers[header]

            request_body = json.dumps(body_json).encode('utf-8')
            logger.info(f"[Proxy] {original_model} → {tier} Provider (API Key) using model: {translated_model}")

        else:
            # Real Anthropic with OAuth
            use_real_anthropic = True
            target_url = f"{ANTHROPIC_BASE_URL}/v1/{endpoint}"
            target_headers = {"Content-Type": "application/json"}

            # Read OAuth token
            oauth_token = get_oauth_token()
            if oauth_token:
                target_headers["Authorization"] = f"Bearer {oauth_token}"
                logger.info(f"[Proxy] {original_model} → Real Anthropic (OAuth) using model: {translated_model}")
            else:
                for k, v in original_headers.items():
                    if k.lower() == "authorization":
                        target_headers["Authorization"] = v
                        break

            # Copy headers including beta features
            if "anthropic-version" in original_headers:
                target_headers["anthropic-version"] = original_headers["anthropic-version"]

            # Pass through beta header as-is
            if "anthropic-beta" in original_headers:
                target_headers["anthropic-beta"] = original_headers["anthropic-beta"]
                logger.info(f"[Proxy] Forwarding beta: {original_headers['anthropic-beta']}")

            # Remove thinking blocks since thinking is disabled
            body_json = fix_thinking_blocks(body_json, has_thinking_beta=False, use_real_anthropic=True)
            request_body = json.dumps(body_json).encode('utf-8')

        # Make the request
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            stream = body_json.get("stream", False)

            if stream:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Proxy] Response status: {response.status_code}")

                if response.status_code != 200:
                    error_text = ""
                    async for chunk in response.aiter_bytes():
                        error_text += chunk.decode('utf-8', errors='ignore')
                        if len(error_text) > 500:
                            break
                    logger.error(f"[Proxy] Error: {error_text[:500]}")

                async def stream_response():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                # Filter headers that should not be forwarded
                # httpx already decompressed the response, so remove content-encoding
                filtered_headers = {k: v for k, v in response.headers.items()
                                    if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']}

                return StreamingResponse(
                    stream_response(),
                    status_code=response.status_code,
                    headers=filtered_headers,
                    media_type="text/event-stream",
                )
            else:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Proxy] Response status: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"[Proxy] Error: {response.text[:500]}")
                    return JSONResponse(
                        content=response.json(),
                        status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    )

                # Strip thinking blocks from response for Real Anthropic OAuth
                response_json = response.json()
                if use_real_anthropic and response_json.get("content"):
                    response_json["content"] = [
                        block for block in response_json["content"]
                        if not (isinstance(block, dict) and block.get("type") in ["thinking", "redacted_thinking"])
                    ]
                    logger.info(f"[Proxy] Stripped thinking blocks from response")

                # Track token usage for successful responses
                try:
                    usage = response_json.get("usage", {})
                    if usage:
                        provider_name = "zai" if provider_type in ["glm", "zai"] else "anthropic" if use_real_anthropic else provider_type
                        token_tracker.record_usage(
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                            provider=provider_name,
                            model=translated_model,
                            tier=tier
                        )
                except Exception as e:
                    logger.warning(f"[TokenTracker] Failed to record usage: {e}")

                return JSONResponse(
                    content=response_json,
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                )

    except Exception as e:
        logger.error(f"[Proxy] Error: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def messages_endpoint(request: Request):
    return await proxy_request(request, "messages")


async def count_tokens_endpoint(request: Request):
    try:
        body = await request.body()
        body_json = json.loads(body) if body else {}
        original_model = body_json.get("model", "claude-sonnet-4-5-20250929")

        api_key, base_url, tier, translated_model, provider_type = get_provider_config(original_model)

        # Update the model in the request body
        body_json["model"] = translated_model

        if not api_key and not base_url:
            return await proxy_request(request, "messages/count_tokens")
        else:
            return JSONResponse(content={"error": "Not supported"}, status_code=501)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def health_check(request: Request):
    antigravity_status = "disabled"
    if ANTIGRAVITY_ENABLED:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{ANTIGRAVITY_BASE_URL}/health")
                antigravity_status = "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            antigravity_status = "not_running"

    return JSONResponse(content={
        "status": "healthy",
        "providers": {
            "zai": {
                "haiku": {"model": ZAI_HAIKU_MODEL, "provider_set": bool(HAIKU_PROVIDER_BASE_URL)},
                "sonnet": {"uses_oauth": not bool(SONNET_PROVIDER_API_KEY), "oauth_token_available": has_oauth_credentials()},
            },
            "antigravity": {
                "enabled": ANTIGRAVITY_ENABLED,
                "status": antigravity_status,
                "port": ANTIGRAVITY_PORT,
                "models": {
                    "sonnet": ANTIGRAVITY_SONNET_MODEL if get_sonnet_provider() == "antigravity" else None,
                    "haiku": ANTIGRAVITY_HAIKU_MODEL if get_haiku_provider() == "antigravity" else None,
                    "opus": ANTIGRAVITY_OPUS_MODEL if get_opus_provider() == "antigravity" else None,
                }
            }
        },
        "routing": {
            "sonnet": get_sonnet_provider(),
            "haiku": get_haiku_provider(),
            "opus": get_opus_provider(),
        }
    })


def load_config():
    """Load configuration from file."""
    global runtime_config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                with config_lock:
                    runtime_config.update(loaded_config)
                    runtime_config["last_updated"] = datetime.now().isoformat()
                logger.info(f"[Config] Loaded configuration from {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"[Config] Failed to load configuration: {e}")
    else:
        # Save initial configuration
        save_config()


def save_config():
    """Save current configuration to file."""
    try:
        with config_lock:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(runtime_config, f, indent=2)
        logger.info(f"[Config] Saved configuration to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"[Config] Failed to save configuration: {e}")


async def get_config_endpoint(request: Request):
    """Get current routing configuration."""
    with config_lock:
        config_copy = runtime_config.copy()

    # Add provider availability info (read from env for custom provider to get latest)
    custom_api_key = os.getenv("CUSTOM_PROVIDER_API_KEY")
    custom_base_url = os.getenv("CUSTOM_PROVIDER_BASE_URL")
    providers_available = {
        "antigravity": ANTIGRAVITY_ENABLED,
        "zai": bool(ZAI_HAIKU_MODEL or ZAI_SONNET_MODEL or ZAI_OPUS_MODEL),
        "anthropic": has_oauth_credentials(),
        "copilot": ENABLE_COPILOT,
        "openrouter": bool(OPENROUTER_API_KEY),
        "custom": bool(custom_api_key and custom_base_url)
    }

    # Available models per provider
    available_models = {
        "antigravity": [
            "gemini-3-pro-high",
            "gemini-3-pro-low",
            "gemini-3-flash",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
            "claude-sonnet-4-5",
            "claude-opus-4-5"
        ],
        "zai": ["glm-4.7"],
        "anthropic": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-3-5-haiku-20241022",
            "claude-opus-4-20250514",
            "claude-opus-4.6",
            "claude-3-7-sonnet-20250219"
        ],
        "copilot": [
            "gpt-4.1",
            "gpt-5-mini",
            "grok-code-fast-1",
            "raptor-mini",
            "claude-haiku-4.5",
            "claude-sonnet-4.5",
            "claude-opus-4.5",
            "gemini-3-flash-preview",
            "gemini-3-pro-preview",
            "gemini-2.5-pro",
            "gpt-5.1-codex-max",
            "gpt-5.1-codex-mini",
            "gpt-5.2-codex"
        ],
        "openrouter": [
            "anthropic/claude-sonnet-4.5",
            "anthropic/claude-haiku-4.5",
            "anthropic/claude-opus-4.5",
            "openai/gpt-4.1",
            "openai/gpt-4o",
            "openai/o1-preview",
            "openai/o1-mini",
            "google/gemini-2.5-pro",
            "google/gemini-2.5-flash",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.3-70b"
        ],
        "custom": build_custom_provider_models()
    }

    return JSONResponse(content={
        "config": config_copy,
        "providers_available": providers_available,
        "available_models": available_models
    })


async def update_config_endpoint(request: Request):
    """Update routing configuration without restart."""
    try:
        body = await request.body()
        updates = json.loads(body) if body else {}

        # Validate provider values
        valid_providers = ["antigravity", "zai", "glm", "anthropic", "copilot", "openrouter", "custom"]
        for tier in ["sonnet_provider", "haiku_provider", "opus_provider"]:
            if tier in updates:
                if updates[tier] not in valid_providers:
                    return JSONResponse(
                        content={"error": f"Invalid provider for {tier}. Must be one of: {valid_providers}"},
                        status_code=400
                    )

        # Update runtime configuration
        with config_lock:
            for key, value in updates.items():
                if key in ["sonnet_provider", "haiku_provider", "opus_provider", "sonnet_model", "haiku_model", "opus_model"]:
                    runtime_config[key] = value
            runtime_config["last_updated"] = datetime.now().isoformat()

        # Save to file
        save_config()

        logger.info(f"[Config] Updated routing configuration: {updates}")

        return JSONResponse(content={
            "status": "success",
            "message": "Configuration updated successfully",
            "config": runtime_config.copy()
        })

    except Exception as e:
        logger.error(f"[Config] Failed to update configuration: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


def load_favorites():
    """Load favorites from file."""
    if FAVORITES_FILE.exists():
        try:
            with open(FAVORITES_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[Favorites] Failed to load favorites: {e}")
    return []


def save_favorites(favorites):
    """Save favorites to file."""
    try:
        with open(FAVORITES_FILE, 'w') as f:
            json.dump(favorites, f, indent=2)
        logger.info(f"[Favorites] Saved favorites to {FAVORITES_FILE}")
    except Exception as e:
        logger.error(f"[Favorites] Failed to save favorites: {e}")


async def get_favorites_endpoint(request: Request):
    """Get all saved favorites."""
    with favorites_lock:
        favorites = load_favorites()
    return JSONResponse(content={"favorites": favorites})


async def save_favorite_endpoint(request: Request):
    """Save a new favorite configuration."""
    try:
        body = await request.body()
        data = json.loads(body) if body else {}

        name = data.get('name', '').strip()
        config = data.get('config', {})

        if not name:
            return JSONResponse(content={"error": "Name is required"}, status_code=400)

        # Validate config has required fields
        required_fields = ['sonnet_provider', 'sonnet_model', 'haiku_provider', 'haiku_model', 'opus_provider', 'opus_model']
        for field in required_fields:
            if field not in config:
                return JSONResponse(content={"error": f"Missing field: {field}"}, status_code=400)

        with favorites_lock:
            favorites = load_favorites()
            favorites.append({
                "name": name,
                "config": config,
                "created_at": datetime.now().isoformat()
            })
            save_favorites(favorites)

        logger.info(f"[Favorites] Saved new favorite: {name}")
        return JSONResponse(content={"status": "success", "favorites": favorites})

    except Exception as e:
        logger.error(f"[Favorites] Failed to save favorite: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def delete_favorite_endpoint(request: Request):
    """Delete a favorite by index."""
    try:
        # Extract index from path
        path = request.url.path
        idx_str = path.split('/')[-1]

        try:
            idx = int(idx_str)
        except ValueError:
            return JSONResponse(content={"error": "Invalid index"}, status_code=400)

        with favorites_lock:
            favorites = load_favorites()
            if 0 <= idx < len(favorites):
                deleted = favorites.pop(idx)
                save_favorites(favorites)
                logger.info(f"[Favorites] Deleted favorite: {deleted.get('name', idx)}")
                return JSONResponse(content={"status": "success", "favorites": favorites})
            else:
                return JSONResponse(content={"error": "Index out of range"}, status_code=404)

    except Exception as e:
        logger.error(f"[Favorites] Failed to delete favorite: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def dashboard_endpoint(request: Request):
    """Serve a simple HTML dashboard for configuration management."""
    dashboard_file = Path(__file__).parent / "dashboard.html"
    if dashboard_file.exists():
        with open(dashboard_file, "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    else:
        return HTMLResponse(content="<html><body><h1>Dashboard not found</h1></body></html>", status_code=404)


async def get_logs_endpoint(request: Request):
    """Get recent log entries."""
    with log_buffer_lock:
        logs = list(log_buffer)
    return JSONResponse(content={"logs": logs})


async def clear_logs_endpoint(request: Request):
    """Clear the log buffer."""
    with log_buffer_lock:
        log_buffer.clear()
    return JSONResponse(content={"status": "cleared"})


async def logs_page_endpoint(request: Request):
    """Serve dedicated logs page."""
    logs_html_path = os.path.join(os.path.dirname(__file__), 'logs.html')
    if os.path.exists(logs_html_path):
        with open(logs_html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return HTMLResponse(content=html)
    else:
        return HTMLResponse(content="<html><body><h1>Logs page not found</h1></body></html>", status_code=404)


async def usage_page_endpoint(request: Request):
    """Serve dedicated usage statistics page."""
    usage_html_path = os.path.join(os.path.dirname(__file__), 'usage-stats.html')
    if os.path.exists(usage_html_path):
        with open(usage_html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return HTMLResponse(content=html)
    else:
        return HTMLResponse(content="<html><body><h1>Usage page not found</h1></body></html>", status_code=404)


async def get_usage_stats_endpoint(request: Request):
    """Get token usage statistics."""
    try:
        stats = token_tracker.get_usage_stats()
        return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"[Usage] Failed to get stats: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def reset_usage_stats_endpoint(request: Request):
    """Reset token usage statistics."""
    try:
        token_tracker.reset_stats()
        logger.info("[Usage] Statistics reset")
        return JSONResponse(content={"status": "success", "message": "Statistics reset successfully"})
    except Exception as e:
        logger.error(f"[Usage] Failed to reset stats: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def test_antigravity_endpoint(request: Request):
    """Test Antigravity with a minimal request."""
    try:
        test_body = {
            "model": "gemini-3-flash",
            "messages": [{"role": "user", "content": "Say hello"}],
            "max_tokens": 100
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": "test",
            "anthropic-version": "2023-06-01"
        }

        logger.info("[Test] Sending minimal test to Antigravity")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ANTIGRAVITY_BASE_URL}/v1/messages",
                headers=headers,
                json=test_body
            )

            logger.info(f"[Test] Response status: {response.status_code}")
            return JSONResponse(content={
                "status": response.status_code,
                "body": response.json() if response.status_code == 200 else response.text
            })
    except Exception as e:
        logger.error(f"[Test] Error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def copilot_usage_proxy(request: Request):
    """Proxy Copilot usage endpoint to avoid CORS issues."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{GITHUB_COPILOT_BASE_URL}/usage")
            if response.status_code == 200:
                return JSONResponse(content=response.json(), headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET",
                })
            return JSONResponse(content={"error": "Copilot usage unavailable"}, status_code=response.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=503)


async def antigravity_health_proxy(request: Request):
    """Proxy Antigravity health endpoint to avoid CORS issues."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ANTIGRAVITY_BASE_URL}/health")
            if response.status_code == 200:
                return JSONResponse(content=response.json(), headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET",
                })
            return JSONResponse(content={"error": "Antigravity health unavailable"}, status_code=response.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=503)


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


