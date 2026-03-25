"""
All HTTP route handler functions for the Claude Code Proxy.
"""

import os
import json
from pathlib import Path
from datetime import datetime

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse, HTMLResponse

from core.config import (
    logger, config_lock, runtime_config, favorites_lock,
    log_buffer, log_buffer_lock,
    REQUEST_TIMEOUT, ANTIGRAVITY_ENABLED, ANTIGRAVITY_BASE_URL,
    ANTIGRAVITY_PORT, ANTIGRAVITY_SONNET_MODEL, ANTIGRAVITY_HAIKU_MODEL, ANTIGRAVITY_OPUS_MODEL,
    ZAI_HAIKU_MODEL, ZAI_SONNET_MODEL, ZAI_OPUS_MODEL,
    HAIKU_PROVIDER_BASE_URL, SONNET_PROVIDER_API_KEY,
    ENABLE_COPILOT, GITHUB_COPILOT_BASE_URL,
    OPENROUTER_API_KEY,
    ANTHROPIC_BASE_URL,
    save_config, build_custom_provider_models,
    get_sonnet_provider, get_haiku_provider, get_opus_provider,
    providers_lock, save_custom_providers,
)
import core.config as config
from core.oauth import get_oauth_token, has_oauth_credentials
from core.routing import get_provider_config
from core.sanitize import is_reasoning_model, filter_beta_header
from core.providers import (
    proxy_to_antigravity, proxy_to_copilot, proxy_to_openrouter, proxy_to_custom,
    token_tracker,
)
from core.copilot import copilot_manager


# ---------------------------------------------------------------------------
# Main proxy logic
# ---------------------------------------------------------------------------

async def proxy_request(request: Request, endpoint: str) -> JSONResponse | StreamingResponse:
    """Main proxy function with complete thinking block support."""
    try:
        body = await request.body()
        body_json = json.loads(body) if body else {}
        original_model = body_json.get("model", "claude-sonnet-4-5-20250929")

        logger.info(f"[Proxy] Incoming request for model: {original_model}")

        api_key, base_url, tier, translated_model, provider_type = get_provider_config(original_model)

        # Bail immediately if the provider is misconfigured
        if provider_type == "misconfigured":
            with config_lock:
                configured_provider = runtime_config.get(f"{tier.lower()}_provider", "unknown")
            error_msg = (
                f"Provider '{configured_provider}' is configured for {tier} but is missing required "
                f"credentials (API key and/or base URL). Please set the appropriate environment "
                f"variables in .env or switch to a different provider via the dashboard."
            )
            logger.error(f"[Proxy] {error_msg}")
            return JSONResponse(
                content={"error": {"type": "configuration_error", "message": error_msg}},
                status_code=503,
            )

        # Strip thinking/redacted_thinking blocks from ALL messages before routing.
        if 'messages' in body_json:
            original_size = len(json.dumps(body_json))
            for message in body_json['messages']:
                if isinstance(message.get('content'), list):
                    message['content'] = [
                        block for block in message['content']
                        if block.get('type') not in ('thinking', 'redacted_thinking')
                    ]
            stripped_size = len(json.dumps(body_json))
            if original_size != stripped_size:
                logger.info(f"[Proxy] Stripped thinking blocks: {original_size/1024:.1f}KB → {stripped_size/1024:.1f}KB")

        # Strip reasoning parameters from request body for non-reasoning models/providers
        if not is_reasoning_model(translated_model, provider_type):
            if 'thinking' in body_json:
                del body_json['thinking']
                logger.info(f"[Proxy] Stripped 'thinking' parameter from request body (model: {translated_model})")
            if 'effort' in body_json:
                del body_json['effort']
                logger.info(f"[Proxy] Stripped 'effort' parameter from request body (model: {translated_model})")

        # Strip [1m] suffix from model name
        if "[1m]" in translated_model:
            translated_model = translated_model.replace("[1m]", "")
            logger.info(f"[Proxy] Stripped [1m] suffix: {original_model} → {translated_model}")

        body_json["model"] = translated_model

        original_headers = dict(request.headers)
        use_real_anthropic = False

        # Route to Antigravity
        if provider_type == "antigravity":
            logger.info(f"[Proxy] {original_model} → Antigravity ({translated_model})")
            return await proxy_to_antigravity(body_json, original_headers, endpoint)

        # Route to GitHub Copilot
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
            return await proxy_to_custom(body_json, original_headers, endpoint, api_key=api_key, base_url=base_url)

        # Route to Z.AI provider
        elif api_key and base_url and provider_type in ["glm", "zai"]:
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

            oauth_token = get_oauth_token()
            if oauth_token:
                target_headers["Authorization"] = f"Bearer {oauth_token}"
                logger.info(f"[Proxy] {original_model} → Real Anthropic (OAuth) using model: {translated_model}")
            else:
                for k, v in original_headers.items():
                    if k.lower() == "authorization":
                        target_headers["Authorization"] = v
                        break

            if "anthropic-version" in original_headers:
                target_headers["anthropic-version"] = original_headers["anthropic-version"]

            if "anthropic-beta" in original_headers:
                filtered_beta = filter_beta_header(original_headers["anthropic-beta"], translated_model, "anthropic")
                if filtered_beta:
                    target_headers["anthropic-beta"] = filtered_beta
                    logger.info(f"[Proxy] Forwarding beta: {filtered_beta}")

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
                    try:
                        error_content = response.json()
                    except json.JSONDecodeError:
                        error_content = {"error": response.text[:1000] or "Unknown error (non-JSON response)"}
                    
                    logger.error(f"[Proxy] Error: {response.text[:500]}")
                    return JSONResponse(
                        content=error_content,
                        status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    )

                response_json = response.json()
                if use_real_anthropic and response_json.get("content"):
                    response_json["content"] = [
                        block for block in response_json["content"]
                        if not (isinstance(block, dict) and block.get("type") in ["thinking", "redacted_thinking"])
                    ]
                    logger.info(f"[Proxy] Stripped thinking blocks from response")

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


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

async def messages_endpoint(request: Request):
    return await proxy_request(request, "messages")


async def count_tokens_endpoint(request: Request):
    try:
        body = await request.body()
        body_json = json.loads(body) if body else {}
        original_model = body_json.get("model", "claude-sonnet-4-5-20250929")

        api_key, base_url, tier, translated_model, provider_type = get_provider_config(original_model)
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

    with config_lock:
        reactors = runtime_config.get("reactors", [])
        routing_status = {r["id"]: r["provider_id"] for r in reactors}

    return JSONResponse(content={
        "status": "healthy",
        "antigravity": {
            "enabled": ANTIGRAVITY_ENABLED,
            "status": antigravity_status,
            "port": ANTIGRAVITY_PORT
        },
        "routing": routing_status,
        "reactors": reactors
    })


async def get_config_endpoint(request: Request):
    """Get current routing configuration."""
    with config_lock:
        config_copy = runtime_config.copy()

    custom_api_key = os.getenv("CUSTOM_PROVIDER_API_KEY")
    custom_base_url = os.getenv("CUSTOM_PROVIDER_BASE_URL")
    providers_available = {
        "antigravity": ANTIGRAVITY_ENABLED,
        "zai": bool(ZAI_HAIKU_MODEL or ZAI_SONNET_MODEL or ZAI_OPUS_MODEL),
        "anthropic": has_oauth_credentials(),
        "copilot": ENABLE_COPILOT,
        "openrouter": bool(OPENROUTER_API_KEY),
        "custom": True  # Always available now as dynamic providers
    }

    # Add dynamic providers to availability
    with providers_lock:
        for provider in config.custom_providers:
            providers_available[provider["id"]] = True

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
        "zai": ["glm-5",
                "glm-4.7"],
        "anthropic": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-3-5-haiku-20241022",
            "claude-opus-4-20250514",
            "claude-opus-4.6",
            "claude-3-7-sonnet-20250219"
        ],
        "copilot": config_copy.get("copilot_models", []),
        "openrouter": [
            "anthropic/claude-sonnet-4.6",
            "anthropic/claude-haiku-4.6",
            "anthropic/claude-opus-4.6",
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

    # Add dynamic providers' models
    with providers_lock:
        for provider in config.custom_providers:
            available_models[provider["id"]] = provider.get("models", [])

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

        valid_providers = ["antigravity", "zai", "glm", "anthropic", "copilot", "openrouter", "custom"]
        for tier in ["sonnet_provider", "haiku_provider", "opus_provider"]:
            if tier in updates:
                if updates[tier] not in valid_providers:
                    return JSONResponse(
                        content={"error": f"Invalid provider for {tier}. Must be one of: {valid_providers}"},
                        status_code=400
                    )

        with config_lock:
            # Handle standard updates
            for key, value in updates.items():
                if key in ["sonnet_provider", "haiku_provider", "opus_provider", "sonnet_model", "haiku_model", "opus_model", "copilot_models"]:
                    runtime_config[key] = value
            
            # Handle reactors updates
            if "reactors" in updates:
                runtime_config["reactors"] = updates["reactors"]
                
            runtime_config["last_updated"] = datetime.now().isoformat()

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


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

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



# ---------------------------------------------------------------------------
# Custom Providers CRUD
# ---------------------------------------------------------------------------

async def get_providers_endpoint(request: Request):
    """Get all custom providers."""
    with providers_lock:
        return JSONResponse(content={"providers": config.custom_providers})


async def add_provider_endpoint(request: Request):
    """Add a new custom provider."""
    try:
        body = await request.body()
        data = json.loads(body) if body else {}

        name = data.get('name', '').strip()
        base_url = data.get('base_url', '').strip()
        api_key = data.get('api_key', '').strip()
        models = data.get('models', [])

        if not name or not base_url:
            return JSONResponse(content={"error": "Name and Base URL are required"}, status_code=400)

        # Generate a simple slug/id from name if not provided
        import re
        p_id = data.get('id') or re.sub(r'[^a-z0-9]', '-', name.lower()).strip('-')
        
        if p_id == "custom":
            return JSONResponse(
                status_code=400,
                content={"error": "The ID 'custom' is reserved for environment-level configuration. Please use a different name."}
            )

        new_provider = {
            "id": p_id,
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "models": models,
            "created_at": datetime.now().isoformat()
        }

        with providers_lock:
            # Check if ID already exists
            if any(p['id'] == p_id for p in config.custom_providers):
                return JSONResponse(content={"error": f"Provider ID '{p_id}' already exists"}, status_code=400)
            
            updated_providers = config.custom_providers + [new_provider]
            save_custom_providers(updated_providers)

        logger.info(f"[Providers] Added new custom provider: {name} ({p_id})")
        return JSONResponse(content={"status": "success", "provider": new_provider})

    except Exception as e:
        logger.error(f"[Providers] Failed to add provider: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def update_provider_endpoint(request: Request):
    """Update an existing custom provider."""
    try:
        p_id = request.path_params.get("id")
        body = await request.body()
        data = json.loads(body) if body else {}

        with providers_lock:
            for i, p in enumerate(config.custom_providers):
                if p['id'] == p_id:
                    # Update fields
                    for key in ['name', 'base_url', 'api_key', 'models']:
                        if key in data:
                            p[key] = data[key]
                    
                    save_custom_providers(config.custom_providers)
                    logger.info(f"[Providers] Updated custom provider: {p_id}")
                    return JSONResponse(content={"status": "success", "provider": p})

        return JSONResponse(content={"error": "Provider not found"}, status_code=404)

    except Exception as e:
        logger.error(f"[Providers] Failed to update provider: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def delete_provider_endpoint(request: Request):
    """Delete a custom provider."""
    try:
        p_id = request.path_params.get("id")
        
        with providers_lock:
            logger.info(f"[Providers] Deleting custom provider with ID: {p_id}")
            initial_count = len(config.custom_providers)
            updated_providers = [p for p in config.custom_providers if p['id'] != p_id]
            
            if len(updated_providers) < initial_count:
                save_custom_providers(updated_providers)
                logger.info(f"[Providers] Deleted custom provider: {p_id}")
                return JSONResponse(content={"status": "success"})
            
        return JSONResponse(content={"error": "Provider not found"}, status_code=404)

    except Exception as e:
        logger.error(f"[Providers] Failed to delete provider: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def providers_page_endpoint(request: Request):
    """Serve dedicated providers management page."""
    providers_html_path = Path(__file__).parent.parent / "providers.html"
    if providers_html_path.exists():
        with open(providers_html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return HTMLResponse(content=html)
    else:
        return HTMLResponse(content="<html><body><h1>Providers page not found</h1></body></html>", status_code=404)


# ---------------------------------------------------------------------------
# Dashboard & pages
# ---------------------------------------------------------------------------

async def dashboard_endpoint(request: Request):
    """Serve a simple HTML dashboard for configuration management."""
    # HTML files are in the server/ root, one level up from api/
    dashboard_file = Path(__file__).parent.parent / "dashboard.html"
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
    # HTML files are in the server/ root, one level up from api/
    logs_html_path = Path(__file__).parent.parent / "logs.html"
    if logs_html_path.exists():
        with open(logs_html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return HTMLResponse(content=html)
    else:
        return HTMLResponse(content="<html><body><h1>Logs page not found</h1></body></html>", status_code=404)


async def usage_page_endpoint(request: Request):
    """Serve dedicated usage statistics page."""
    # HTML files are in the server/ root, one level up from api/
    usage_html_path = Path(__file__).parent.parent / "usage-stats.html"
    if usage_html_path.exists():
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


# ---------------------------------------------------------------------------
# Copilot Auth Endpoints
# ---------------------------------------------------------------------------

async def copilot_login_start(request: Request):
    """Initiate GitHub device code flow."""
    try:
        data = await copilot_manager.get_device_code()
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"[Copilot] Failed to start login: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def copilot_login_poll(request: Request):
    """Poll for GitHub access token."""
    try:
        device_code = request.query_params.get("device_code")
        if not device_code:
            return JSONResponse(content={"error": "device_code is required"}, status_code=400)
            
        result = await copilot_manager.poll_for_token(device_code)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"[Copilot] Failed to poll for token: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def copilot_status(request: Request):
    """Check Copilot authentication status."""
    github_token = config.runtime_config.get("copilot_github_token")
    has_copilot_token = bool(config.runtime_config.get("copilot_access_token"))
    expires_at = config.runtime_config.get("copilot_expires_at", 0)
    
    logger.info(f"[Copilot] Status request. Authenticated: {bool(github_token)}")
    
    return JSONResponse(content={
        "authenticated": bool(github_token),
        "has_copilot_token": has_copilot_token,
        "expires_at": expires_at,
        "enabled": config.ENABLE_COPILOT
    })
