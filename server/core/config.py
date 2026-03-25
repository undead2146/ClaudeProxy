"""
Configuration & shared state for Claude Code Proxy.

All environment variables, runtime config, logger setup, and shared constants.
"""

import os
import sys
import json
import logging
import threading
from pathlib import Path
from datetime import datetime
from collections import deque

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
PROXY_API_KEY = os.getenv("PROXY_API_KEY")

# ---------------------------------------------------------------------------
# Provider API keys & base URLs
# ---------------------------------------------------------------------------
HAIKU_PROVIDER_API_KEY = os.getenv("HAIKU_PROVIDER_API_KEY")
HAIKU_PROVIDER_BASE_URL = os.getenv("HAIKU_PROVIDER_BASE_URL")
OPUS_PROVIDER_API_KEY = os.getenv("OPUS_PROVIDER_API_KEY")
OPUS_PROVIDER_BASE_URL = os.getenv("OPUS_PROVIDER_BASE_URL")
SONNET_PROVIDER_API_KEY = os.getenv("SONNET_PROVIDER_API_KEY")
SONNET_PROVIDER_BASE_URL = os.getenv("SONNET_PROVIDER_BASE_URL")

# ---------------------------------------------------------------------------
# Z.AI/GLM model mappings
# ---------------------------------------------------------------------------
ZAI_HAIKU_MODEL = os.getenv("GLM_HAIKU_MODEL") or os.getenv("ZAI_HAIKU_MODEL", "glm-4.7")
ZAI_SONNET_MODEL = os.getenv("GLM_SONNET_MODEL") or os.getenv("ZAI_SONNET_MODEL", "glm-4.7")
ZAI_OPUS_MODEL = os.getenv("GLM_OPUS_MODEL") or os.getenv("ZAI_OPUS_MODEL", "glm-4.7")

# ---------------------------------------------------------------------------
# Antigravity configuration
# ---------------------------------------------------------------------------
ANTIGRAVITY_ENABLED = os.getenv("ANTIGRAVITY_ENABLED", "false").lower() == "true"
ANTIGRAVITY_PORT = int(os.getenv("ANTIGRAVITY_PORT", "8081"))
ANTIGRAVITY_BASE_URL = f"http://localhost:{ANTIGRAVITY_PORT}"
ANTIGRAVITY_CONFIG_DIR = os.getenv("ANTIGRAVITY_CONFIG_DIR", ".antigravity")

ANTIGRAVITY_SONNET_MODEL = os.getenv("ANTIGRAVITY_SONNET_MODEL", "gemini-3-pro-high")
ANTIGRAVITY_HAIKU_MODEL = os.getenv("ANTIGRAVITY_HAIKU_MODEL", "gemini-3-flash")
ANTIGRAVITY_OPUS_MODEL = os.getenv("ANTIGRAVITY_OPUS_MODEL", "gemini-3-pro-high")

# ---------------------------------------------------------------------------
# GitHub Copilot configuration
# ---------------------------------------------------------------------------
ENABLE_COPILOT = os.getenv("ENABLE_COPILOT", "true").lower() == "true"
GITHUB_CLIENT_ID = "Iv1.b507a08c87ecfe98"
GITHUB_BASE_URL = "https://github.com"
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_COPILOT_API_URL = "https://api.githubcopilot.com"
GITHUB_COPILOT_BASE_URL = os.getenv("GITHUB_COPILOT_BASE_URL", GITHUB_COPILOT_API_URL)
GITHUB_COPILOT_SONNET_MODEL = os.getenv("GITHUB_COPILOT_SONNET_MODEL", "claude-sonnet-4.6")
GITHUB_COPILOT_HAIKU_MODEL = os.getenv("GITHUB_COPILOT_HAIKU_MODEL", "claude-haiku-4.6")
GITHUB_COPILOT_OPUS_MODEL = os.getenv("GITHUB_COPILOT_OPUS_MODEL", "claude-opus-4.6")

# ---------------------------------------------------------------------------
# OpenRouter configuration
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api")
OPENROUTER_SONNET_MODEL = os.getenv("OPENROUTER_SONNET_MODEL", "anthropic/claude-sonnet-4.6")
OPENROUTER_HAIKU_MODEL = os.getenv("OPENROUTER_HAIKU_MODEL", "anthropic/claude-haiku-4.6")
OPENROUTER_OPUS_MODEL = os.getenv("OPENROUTER_OPUS_MODEL", "anthropic/claude-opus-4.6")

# ---------------------------------------------------------------------------
# Custom provider configuration
# ---------------------------------------------------------------------------
CUSTOM_PROVIDER_API_KEY = os.getenv("CUSTOM_PROVIDER_API_KEY")
CUSTOM_PROVIDER_BASE_URL = os.getenv("CUSTOM_PROVIDER_BASE_URL")
CUSTOM_PROVIDER_SONNET_MODEL = os.getenv("CUSTOM_PROVIDER_SONNET_MODEL", "claude-sonnet-4.5")
CUSTOM_PROVIDER_HAIKU_MODEL = os.getenv("CUSTOM_PROVIDER_HAIKU_MODEL", "claude-sonnet-4.5")
CUSTOM_PROVIDER_OPUS_MODEL = os.getenv("CUSTOM_PROVIDER_OPUS_MODEL", "claude-sonnet-4.5")

# ---------------------------------------------------------------------------
# Anthropic (OAuth) default model mappings
# ---------------------------------------------------------------------------
ANTHROPIC_SONNET_MODEL = os.getenv("ANTHROPIC_SONNET_MODEL", "claude-sonnet-4-5-20250929")
ANTHROPIC_HAIKU_MODEL = os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-3-5-haiku-20241022")
ANTHROPIC_OPUS_MODEL = os.getenv("ANTHROPIC_OPUS_MODEL", "claude-opus-4-20250514")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

# ---------------------------------------------------------------------------
# Provider routing (env defaults)
# ---------------------------------------------------------------------------
SONNET_PROVIDER = os.getenv("SONNET_PROVIDER", "antigravity")
HAIKU_PROVIDER = os.getenv("HAIKU_PROVIDER", "antigravity")
OPUS_PROVIDER = os.getenv("OPUS_PROVIDER", "anthropic")

# ---------------------------------------------------------------------------
# Server settings
# ---------------------------------------------------------------------------
PROXY_PORT = int(os.getenv("PROXY_PORT", "8082"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
CONFIG_FILE = Path("config.json")
FAVORITES_FILE = Path("favorites.json")
CUSTOM_PROVIDERS_FILE = Path("custom_providers.json")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_file = os.getenv("CLAUDE_PROXY_LOG_FILE")
logging_config = {
    "level": logging.INFO,
    "format": "%(asctime)s - %(levelname)s - %(message)s",
}

if log_file:
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    logging_config["filename"] = log_file
    logging_config["filemode"] = "a"
else:
    logging_config["stream"] = sys.stdout

logging.basicConfig(**logging_config)
logger = logging.getLogger("claude_proxy")

# In-memory log buffer (last 100 entries)
log_buffer = deque(maxlen=100)
log_buffer_lock = threading.Lock()


class BufferHandler(logging.Handler):
    """Custom handler to capture logs in memory."""
    def emit(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": self.format(record)
        }
        with log_buffer_lock:
            log_buffer.append(log_entry)


buffer_handler = BufferHandler()
buffer_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(buffer_handler)

# ---------------------------------------------------------------------------
# Runtime configuration (thread-safe)
# ---------------------------------------------------------------------------
config_lock = threading.RLock()
favorites_lock = threading.RLock()
providers_lock = threading.RLock()

custom_providers = []

runtime_config = {
    "sonnet_provider": os.getenv("SONNET_PROVIDER", "antigravity"),
    "haiku_provider": os.getenv("HAIKU_PROVIDER", "antigravity"),
    "opus_provider": os.getenv("OPUS_PROVIDER", "anthropic"),
    "sonnet_model": os.getenv("ANTIGRAVITY_SONNET_MODEL", "gemini-3-pro-high"),
    "haiku_model": os.getenv("ANTIGRAVITY_HAIKU_MODEL", "gemini-3-flash"),
    "opus_model": os.getenv("ANTIGRAVITY_OPUS_MODEL", "gemini-3-pro-high"),
    "copilot_github_token": None,
    "copilot_access_token": None,
    "copilot_expires_at": 0,
    "copilot_models": [
        "gpt-4.1", "gpt-5-mini", "grok-code-fast-1", "raptor-mini",
        "claude-haiku-4.6", "claude-sonnet-4.6", "claude-opus-4.6",
        "gemini-3-flash-preview", "gemini-3-pro-preview", "gemini-2.5-pro",
        "gpt-5.1-codex-max", "gpt-5.1-codex-mini", "gpt-5.2-codex"
    ],
    "reactors": [
        {
            "id": "sonnet",
            "label": "Sonnet",
            "pattern": "sonnet",
            "provider_id": os.getenv("SONNET_PROVIDER", "antigravity"),
            "model": os.getenv("ANTIGRAVITY_SONNET_MODEL", "gemini-3-pro-high"),
            "theme": "#ffaa00"
        },
        {
            "id": "haiku",
            "label": "Haiku",
            "pattern": "haiku",
            "provider_id": os.getenv("HAIKU_PROVIDER", "antigravity"),
            "model": os.getenv("ANTIGRAVITY_HAIKU_MODEL", "gemini-3-flash"),
            "theme": "#00ffaa"
        },
        {
            "id": "opus",
            "label": "Opus",
            "pattern": "opus",
            "provider_id": os.getenv("OPUS_PROVIDER", "anthropic"),
            "model": os.getenv("ANTIGRAVITY_OPUS_MODEL", "gemini-3-pro-high"),
            "theme": "#aa00ff"
        }
    ],
    "last_updated": datetime.now().isoformat()
}


def get_sonnet_provider():
    with config_lock:
        return runtime_config.get("sonnet_provider", SONNET_PROVIDER)

def get_haiku_provider():
    with config_lock:
        return runtime_config.get("haiku_provider", HAIKU_PROVIDER)

def get_opus_provider():
    with config_lock:
        return runtime_config.get("opus_provider", OPUS_PROVIDER)

def load_config():
    """Load configuration from file."""
    global runtime_config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded_config = json.load(f)
                with config_lock:
                    runtime_config.update(loaded_config)
                    runtime_config["last_updated"] = datetime.now().isoformat()
                logger.info(f"[Config] Loaded configuration from {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"[Config] Failed to load configuration: {e}")
    else:
        save_config()

    load_custom_providers()


def load_custom_providers():
    """Load custom providers from file."""
    global custom_providers
    if CUSTOM_PROVIDERS_FILE.exists():
        try:
            with open(CUSTOM_PROVIDERS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                with providers_lock:
                    custom_providers = loaded
                logger.info(f"[Config] Loaded {len(custom_providers)} custom providers from {CUSTOM_PROVIDERS_FILE}")
        except Exception as e:
            logger.error(f"[Config] Failed to load custom providers: {e}")
    else:
        # Create empty file if it doesn't exist
        save_custom_providers([])


def save_custom_providers(providers):
    """Save custom providers to file."""
    global custom_providers
    try:
        with providers_lock:
            custom_providers = providers
            with open(CUSTOM_PROVIDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(custom_providers, f, indent=2)
        logger.info(f"[Config] Saved custom providers to {CUSTOM_PROVIDERS_FILE}")
    except Exception as e:
        logger.error(f"[Config] Failed to save custom providers: {e}")


def save_config():
    """Save current configuration to file."""
    try:
        with config_lock:
            with open(CONFIG_FILE, "w") as f:
                json.dump(runtime_config, f, indent=2)
        logger.info(f"[Config] Saved configuration to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"[Config] Failed to save configuration: {e}")


def build_custom_provider_models() -> list:
    """Build the custom provider models list from environment variables."""
    # Latest and best models only
    models = [
        # Claude (latest only)
        "claude-opus-4.6",
        "claude-sonnet-4.6",
        "claude-haiku-4.6",

        # DeepSeek
        "deepseek-v3.2",

        # enowX Labs
        "enowx-default",

        # Google Gemini (latest only)
        "gemini-3.1-pro",
        "gemini-3.0-pro",
        "gemini-2.5-pro",

        # Zhipu
        "glm-5.0",

        # OpenAI (latest only)
        "gpt-5.4",
        "gpt-5.3-codex",

        # Kimi
        "kimi-k2.5",

        # Minimax
        "minimax-m1",
    ]

    # Allow environment variable overrides for the main three tiers
    sonnet_model = os.getenv("CUSTOM_PROVIDER_SONNET_MODEL")
    haiku_model = os.getenv("CUSTOM_PROVIDER_HAIKU_MODEL")
    opus_model = os.getenv("CUSTOM_PROVIDER_OPUS_MODEL")

    if sonnet_model and sonnet_model not in models:
        models.append(sonnet_model)
    if haiku_model and haiku_model not in models:
        models.append(haiku_model)
    if opus_model and opus_model not in models:
        models.append(opus_model)

    # Add models from dynamic custom providers
    with providers_lock:
        for provider in custom_providers:
            p_models = provider.get("models", [])
            for m in p_models:
                if m and m not in models:
                    models.append(m)

    # Remove duplicates while preserving order
    seen = set()
    unique_models = []
    for model in models:
        if model not in seen:
            seen.add(model)
            unique_models.append(model)

    return unique_models
