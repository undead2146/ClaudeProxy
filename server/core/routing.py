"""
Provider routing logic — determines which backend to send each request to.
"""

import os
from typing import Optional, Tuple
import core.config as config
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
    # OpenRouter
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    # Custom
    CUSTOM_PROVIDER_API_KEY, CUSTOM_PROVIDER_BASE_URL,
    providers_lock,
)

def determine_model_tier(model: str) -> str:
    """Categorize the requested model into one of the configured reactors."""
    m = model.lower()
    
    with config.config_lock:
        reactors = config.runtime_config.get("reactors", [])
        
        # 1. Try exact matches on configured model names first (legacy/Z.AI/Antigravity)
        if ZAI_HAIKU_MODEL and model == ZAI_HAIKU_MODEL: return "haiku"
        if ZAI_SONNET_MODEL and model == ZAI_SONNET_MODEL: return "sonnet"
        if ZAI_OPUS_MODEL and model == ZAI_OPUS_MODEL: return "opus"
        if ANTIGRAVITY_HAIKU_MODEL and model == ANTIGRAVITY_HAIKU_MODEL: return "haiku"
        if ANTIGRAVITY_SONNET_MODEL and model == ANTIGRAVITY_SONNET_MODEL: return "sonnet"
        if ANTIGRAVITY_OPUS_MODEL and model == ANTIGRAVITY_OPUS_MODEL: return "opus"
        
        # 2. Match against dynamic reactor patterns (Longest match first for priority)
        sorted_reactors = sorted(reactors, key=lambda r: len(r.get("pattern", "")), reverse=True)
        for r in sorted_reactors:
            pattern = r.get("pattern", "").lower()
            if pattern and pattern in m:
                return r["id"]
                
    # Default fallback
    if "haiku" in m or "flash" in m or "gemini" in m: return "haiku"
    if "opus" in m: return "opus"
    return "sonnet"

def get_provider_config(model: str) -> Tuple[Optional[str], Optional[str], str, str, str]:
    """Determine which provider to use based on model name.
    Returns: (api_key, base_url, reactor_id, translated_model, provider_type)
    """
    reactor_id = determine_model_tier(model)
    
    with config_lock:
        reactors = runtime_config.get("reactors", [])
        reactor = next((r for r in reactors if r["id"] == reactor_id), None)
        
        if not reactor:
            # Emergency fallback to old config structure if reactors list is missing
            provider_id = runtime_config.get(f"{reactor_id}_provider", "antigravity")
            target_model = runtime_config.get(f"{reactor_id}_model", model)
        else:
            provider_id = reactor["provider_id"]
            target_model = reactor["model"] or model

    # Route based on provider_id
    # 1. Anthropic (Direct/OAuth)
    if provider_id == "anthropic":
        logger.info(f"[Proxy] Routing {reactor_id.upper()} → Anthropic (Direct/OAuth)")
        target_model = target_model or model
        return None, None, reactor_id, target_model, "anthropic"

    # 2. Antigravity (Google Provider)
    if provider_id == "antigravity":
        logger.info(f"[Proxy] Routing {reactor_id.upper()} → Antigravity ({target_model})")
        return None, ANTIGRAVITY_BASE_URL, reactor_id, target_model, "antigravity"

    # 3. Copilot
    if provider_id == "copilot":
        logger.info(f"[Proxy] Routing {reactor_id.upper()} → GitHub Copilot ({target_model})")
        return None, GITHUB_COPILOT_BASE_URL, reactor_id, target_model, "copilot"

    # 4. OpenRouter
    if provider_id == "openrouter":
        logger.info(f"[Proxy] Routing {reactor_id.upper()} → OpenRouter ({target_model})")
        return OPENROUTER_API_KEY, OPENROUTER_BASE_URL, reactor_id, target_model, "openrouter"

    # 5. Z.AI / GLM (Legacy fallback)
    if provider_id in ["glm", "zai"]:
         api_key = SONNET_PROVIDER_API_KEY if reactor_id == "sonnet" else \
                  HAIKU_PROVIDER_API_KEY if reactor_id == "haiku" else \
                  OPUS_PROVIDER_API_KEY
         base_url = SONNET_PROVIDER_BASE_URL if reactor_id == "sonnet" else \
                   HAIKU_PROVIDER_BASE_URL if reactor_id == "haiku" else \
                   OPUS_PROVIDER_BASE_URL
         logger.info(f"[Proxy] Routing {reactor_id.upper()} → Z.AI ({target_model})")
         return api_key, base_url, reactor_id, target_model, "zai"

    # 6. Custom Providers
    # Check for hardcoded 'custom' from .env
    if provider_id == "custom":
        if CUSTOM_PROVIDER_API_KEY and CUSTOM_PROVIDER_BASE_URL:
            logger.info(f"[Proxy] Routing {reactor_id.upper()} → Hardcoded Custom Provider ({target_model})")
            return CUSTOM_PROVIDER_API_KEY, CUSTOM_PROVIDER_BASE_URL, reactor_id, target_model, "custom"

    # Check dynamic custom providers
    with providers_lock:
        for p in config.custom_providers:
            if provider_id == p["id"]:
                logger.info(f"[Proxy] Routing {reactor_id.upper()} → {p['name']} ({target_model})")
                return p["api_key"], p["base_url"], reactor_id, target_model, "custom"

    # Provider is set but prerequisites are missing — return error
    logger.error(f"[Proxy] Reactor '{reactor_id}' uses unknown or misconfigured provider '{provider_id}'")
    return None, None, reactor_id, target_model, "misconfigured"
