"""
Provider routing logic — determines which backend to send each request to.
"""

import os
from typing import Optional, Tuple

from core.config import (
    logger, config_lock, runtime_config,
    # Z.AI
    ZAI_HAIKU_MODEL, ZAI_SONNET_MODEL, ZAI_OPUS_MODEL,
    HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL,
    SONNET_PROVIDER_API_KEY, SONNET_PROVIDER_BASE_URL,
    OPUS_PROVIDER_API_KEY, OPUS_PROVIDER_BASE_URL,
    # Antigravity
    ANTIGRAVITY_ENABLED, ANTIGRAVITY_BASE_URL,
    ANTIGRAVITY_SONNET_MODEL, ANTIGRAVITY_HAIKU_MODEL, ANTIGRAVITY_OPUS_MODEL,
    # Copilot
    ENABLE_COPILOT, GITHUB_COPILOT_BASE_URL,
    GITHUB_COPILOT_SONNET_MODEL, GITHUB_COPILOT_HAIKU_MODEL, GITHUB_COPILOT_OPUS_MODEL,
    # OpenRouter
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    OPENROUTER_SONNET_MODEL, OPENROUTER_HAIKU_MODEL, OPENROUTER_OPUS_MODEL,
    # Anthropic
    ANTHROPIC_HAIKU_MODEL,
    # Provider getters
    get_sonnet_provider, get_haiku_provider, get_opus_provider,
    build_custom_provider_models,
)


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
        if "5" in model_lower or "flash" in model_lower:
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
        elif current_sonnet_provider in ["glm", "zai"] and SONNET_PROVIDER_API_KEY and SONNET_PROVIDER_BASE_URL:
            zai_model = sonnet_model if sonnet_model else ZAI_SONNET_MODEL
            logger.info(f"[Proxy] Routing Sonnet → Z.AI ({zai_model})")
            return SONNET_PROVIDER_API_KEY, SONNET_PROVIDER_BASE_URL, tier, zai_model, "zai"
        elif current_sonnet_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Sonnet  GitHub Copilot ({sonnet_model})")
            return None, GITHUB_COPILOT_BASE_URL, tier, sonnet_model, "copilot"
        elif current_sonnet_provider == "openrouter" and OPENROUTER_API_KEY:
            logger.info(f"[Proxy] Routing Sonnet  OpenRouter ({OPENROUTER_SONNET_MODEL})")
            return OPENROUTER_API_KEY, OPENROUTER_BASE_URL, tier, OPENROUTER_SONNET_MODEL, "openrouter"
        elif current_sonnet_provider == "custom":
            custom_api_key = os.getenv("CUSTOM_PROVIDER_API_KEY")
            custom_base_url = os.getenv("CUSTOM_PROVIDER_BASE_URL")
            custom_sonnet_model = os.getenv("CUSTOM_PROVIDER_SONNET_MODEL", "claude-sonnet-4.5")
            if custom_api_key and custom_base_url:
                logger.info(f"[Proxy] Routing Sonnet  Custom Provider ({custom_sonnet_model})")
                return custom_api_key, custom_base_url, tier, custom_sonnet_model, "custom"

        # Fallback — either anthropic was explicitly chosen, or the chosen provider is misconfigured
        if current_sonnet_provider == "anthropic":
            logger.info(f"[Proxy] Routing Sonnet → Anthropic (OAuth) using original model: {model}")
            return None, None, tier, model, "anthropic"

        # Provider is set but prerequisites are missing — return error, don't silently reroute
        logger.error(f"[Proxy] Sonnet provider '{current_sonnet_provider}' is configured but missing API key or prerequisites")
        return None, None, tier, model, "misconfigured"

    elif tier == "Haiku":
        if current_haiku_provider == "antigravity" and ANTIGRAVITY_ENABLED:
            logger.info(f"[Proxy] Routing Haiku  Antigravity ({haiku_model})")
            return None, ANTIGRAVITY_BASE_URL, tier, haiku_model, "antigravity"
        elif current_haiku_provider in ["glm", "zai"] and HAIKU_PROVIDER_API_KEY and HAIKU_PROVIDER_BASE_URL:
            zai_model = haiku_model if haiku_model else ZAI_HAIKU_MODEL
            logger.info(f"[Proxy] Routing Haiku → Z.AI ({zai_model})")
            return HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL, tier, zai_model, "zai"
        elif current_haiku_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Haiku  GitHub Copilot ({haiku_model})")
            return None, GITHUB_COPILOT_BASE_URL, tier, haiku_model, "copilot"
        elif current_haiku_provider == "openrouter" and OPENROUTER_API_KEY:
            logger.info(f"[Proxy] Routing Haiku  OpenRouter ({OPENROUTER_HAIKU_MODEL})")
            return OPENROUTER_API_KEY, OPENROUTER_BASE_URL, tier, OPENROUTER_HAIKU_MODEL, "openrouter"
        elif current_haiku_provider == "custom":
            custom_api_key = os.getenv("CUSTOM_PROVIDER_API_KEY")
            custom_base_url = os.getenv("CUSTOM_PROVIDER_BASE_URL")
            custom_haiku_model = os.getenv("CUSTOM_PROVIDER_HAIKU_MODEL", "claude-haiku-4.5")
            if custom_api_key and custom_base_url:
                logger.info(f"[Proxy] Routing Haiku  Custom Provider ({custom_haiku_model})")
                return custom_api_key, custom_base_url, tier, custom_haiku_model, "custom"

        if current_haiku_provider == "anthropic":
            logger.info(f"[Proxy] Routing Haiku → Anthropic (OAuth) using original model: {model}")
            return None, None, tier, model, "anthropic"

        logger.error(f"[Proxy] Haiku provider '{current_haiku_provider}' is configured but missing API key or prerequisites")
        return None, None, tier, model, "misconfigured"

    elif tier == "Opus":
        if current_opus_provider == "antigravity" and ANTIGRAVITY_ENABLED:
            logger.info(f"[Proxy] Routing Opus  Antigravity ({opus_model})")
            return None, ANTIGRAVITY_BASE_URL, tier, opus_model, "antigravity"
        elif current_opus_provider in ["glm", "zai"] and OPUS_PROVIDER_API_KEY and OPUS_PROVIDER_BASE_URL:
            zai_model = opus_model if opus_model else ZAI_OPUS_MODEL
            logger.info(f"[Proxy] Routing Opus → Z.AI ({zai_model})")
            return OPUS_PROVIDER_API_KEY, OPUS_PROVIDER_BASE_URL, tier, zai_model, "zai"
        elif current_opus_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Opus ? GitHub Copilot ({GITHUB_COPILOT_OPUS_MODEL})")
            return None, GITHUB_COPILOT_BASE_URL, tier, GITHUB_COPILOT_OPUS_MODEL, "copilot"
        elif current_opus_provider == "openrouter" and OPENROUTER_API_KEY:
            logger.info(f"[Proxy] Routing Opus  OpenRouter ({OPENROUTER_OPUS_MODEL})")
            return OPENROUTER_API_KEY, OPENROUTER_BASE_URL, tier, OPENROUTER_OPUS_MODEL, "openrouter"
        elif current_opus_provider == "custom":
            custom_api_key = os.getenv("CUSTOM_PROVIDER_API_KEY")
            custom_base_url = os.getenv("CUSTOM_PROVIDER_BASE_URL")
            custom_opus_model = os.getenv("CUSTOM_PROVIDER_OPUS_MODEL", "claude-opus-4.5")
            if custom_api_key and custom_base_url:
                logger.info(f"[Proxy] Routing Opus  Custom Provider ({custom_opus_model})")
                return custom_api_key, custom_base_url, tier, custom_opus_model, "custom"

        if current_opus_provider == "anthropic":
            logger.info(f"[Proxy] Routing Opus → Anthropic (OAuth) using original model: {model}")
            return None, None, tier, model, "anthropic"

        logger.error(f"[Proxy] Opus provider '{current_opus_provider}' is configured but missing API key or prerequisites")
        return None, None, tier, model, "misconfigured"

    # Unknown model - default to Haiku routing
    logger.warning(f"[Proxy] Unknown model tier for '{model}', defaulting to Haiku tier")
    current_haiku_provider = get_haiku_provider()
    if current_haiku_provider == "antigravity" and ANTIGRAVITY_ENABLED:
        return None, ANTIGRAVITY_BASE_URL, "Haiku", ANTIGRAVITY_HAIKU_MODEL, "antigravity"
    elif current_haiku_provider in ["glm", "zai"] and HAIKU_PROVIDER_API_KEY and HAIKU_PROVIDER_BASE_URL:
        return HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL, "Haiku", haiku_model or ZAI_HAIKU_MODEL, "zai"
    elif current_haiku_provider == "copilot" and ENABLE_COPILOT:
        return None, GITHUB_COPILOT_BASE_URL, "Haiku", haiku_model, "copilot"
    else:
        return None, None, "Unknown", ANTHROPIC_HAIKU_MODEL, "anthropic"
