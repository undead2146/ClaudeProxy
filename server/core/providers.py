"""
Provider proxy functions — forward requests to each backend provider.
"""

import os
import json

import httpx
from starlette.responses import JSONResponse, StreamingResponse

from core.config import (
    logger, REQUEST_TIMEOUT,
    ANTIGRAVITY_BASE_URL,
    GITHUB_COPILOT_BASE_URL, GITHUB_COPILOT_API_URL,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    CUSTOM_PROVIDER_API_KEY, CUSTOM_PROVIDER_BASE_URL,
)
from core.sanitize import filter_beta_header, sanitize_for_custom, fix_streaming_tool_inputs, redact_text
from core.copilot import copilot_manager
from core.convert import convert_anthropic_to_openai, convert_openai_to_anthropic, convert_openai_stream_to_anthropic_async
from services.token_tracker import TokenUsageTracker

token_tracker = TokenUsageTracker()


async def proxy_to_antigravity(body_json: dict, original_headers: dict, endpoint: str) -> JSONResponse | StreamingResponse:
    """Proxy request to Antigravity server."""
    try:
        target_url = f"{ANTIGRAVITY_BASE_URL}/v1/{endpoint}"
        target_headers = {
            "Content-Type": "application/json",
            "x-api-key": "test",
            "anthropic-version": "2023-06-01"
        }

        logger.info(f"[Antigravity] Sending to {target_url}")
        logger.info(f"[Antigravity] Model in body: {body_json.get('model')}")
        logger.info(f"[Antigravity] Stream: {body_json.get('stream', False)}")
        logger.info(f"[Antigravity] Max tokens: {body_json.get('max_tokens', 'not set')}")
        logger.info(f"[Antigravity] Messages count: {len(body_json.get('messages', []))}")

        messages = body_json.get('messages', [])
        if messages:
            first_msg = messages[0]
            content_preview = str(first_msg.get('content', ''))[:100]
            logger.info(f"[Antigravity] First message role: {first_msg.get('role')}, content preview: {content_preview}")

        if "anthropic-beta" in original_headers:
            filtered_beta = filter_beta_header(original_headers["anthropic-beta"], body_json.get('model', ''), "antigravity")
            if filtered_beta:
                target_headers["anthropic-beta"] = filtered_beta
                logger.info(f"[Antigravity] Beta header (filtered): {target_headers['anthropic-beta']}")
            else:
                logger.info(f"[Antigravity] All beta features filtered out or none relevant")

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
    """Proxy request to GitHub Copilot API using local authentication."""
    try:
        # Get valid Copilot token
        token = await copilot_manager.get_copilot_token()
        if not token:
            logger.error("[Copilot] No valid Copilot token found. User needs to login.")
            return JSONResponse(content={
                "error": "Not authenticated with GitHub Copilot",
                "message": "Please go to the dashboard and login with GitHub."
            }, status_code=401)

        is_chat = endpoint in ["messages", "chat/completions"]
        if is_chat and "messages" in body_json:
            original_model = body_json.get("model", "unknown")
            body_json = convert_anthropic_to_openai(body_json)
            # Map the model to a valid Copilot ID
            body_json["model"] = copilot_manager.map_model(body_json.get("model", original_model))
            # Ensure we use the converted model or fallback
            logger.info(f"[Copilot] Converted Anthropic payload to OpenAI. Mapped Model: {body_json.get('model')} (was {original_model})")
            if endpoint == "messages":
                endpoint = "chat/completions"

        # Construct target URL
        base_url = GITHUB_COPILOT_BASE_URL if GITHUB_COPILOT_BASE_URL != "http://localhost:4141" else GITHUB_COPILOT_API_URL
        
        # GitHub's official API does not use the /v1 prefix for chat/completions
        if base_url == GITHUB_COPILOT_API_URL:
            target_url = f"{base_url.rstrip('/')}/{endpoint}"
        else:
            target_url = f"{base_url.rstrip('/')}/v1/{endpoint}"
        
        # Prepare headers
        vision = any(
            isinstance(m.get('content'), list) and any(b.get('type') == 'image_url' for b in m['content'])
            for m in body_json.get('messages', [])
        )
        
        session_id = original_headers.get("x-interaction-id") or original_headers.get("X-Interaction-Id")
        initiator = original_headers.get("x-initiator") or original_headers.get("X-Initiator") or "user"
        
        target_headers = copilot_manager.get_headers(
            token=token,
            vision=vision,
            initiator=initiator,
            session_id=session_id
        )

        if "anthropic-version" in original_headers:
            target_headers["anthropic-version"] = original_headers["anthropic-version"]

        if "anthropic-beta" in original_headers:
            target_headers["anthropic-beta"] = filter_beta_header(original_headers["anthropic-beta"], body_json.get('model', ''), "copilot")

        logger.info(f"[Copilot] Sending to {target_url}")
        request_body = json.dumps(body_json).encode('utf-8')

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            stream = body_json.get("stream", False)

            if stream:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Copilot] Response status (stream): {response.status_code}")

                if response.status_code == 401:
                    logger.warning("[Copilot] 401 Unauthorized - clearing token cache")
                    with config_lock:
                        runtime_config["copilot_access_token"] = None
                        save_config()

                if response.status_code != 200:
                    error_text = redact_text(response.text)
                    logger.error(f"[Copilot] Error: {error_text[:500]}")
                    return JSONResponse(content={"error": error_text}, status_code=response.status_code)

                # Return converted stream
                return StreamingResponse(
                    convert_openai_stream_to_anthropic_async(response.aiter_bytes(), model=body_json.get("model", "unknown")),
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    media_type="text/event-stream",
                )
            else:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Copilot] Response status: {response.status_code}")

                if response.status_code == 401:
                    logger.warning("[Copilot] 401 Unauthorized - clearing token cache")
                    with config_lock:
                        runtime_config["copilot_access_token"] = None
                        save_config()

                if response.status_code != 200:
                    error_text = redact_text(response.text)
                    logger.error(f"[Copilot] Error: {error_text[:500]}")
                    return JSONResponse(
                        content=response.json() if response.headers.get("content-type") == "application/json" else {"error": error_text},
                        status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    )

                # Convert response back to Anthropic format
                response_data = response.json()
                anthropic_response = convert_openai_to_anthropic(response_data)
                
                # Record usage
                try:
                    usage = response_data.get("usage", {})
                    if usage:
                        token_tracker.record_usage(
                            input_tokens=usage.get("prompt_tokens", 0),
                            output_tokens=usage.get("completion_tokens", 0),
                            provider="copilot",
                            model=body_json.get("model", "unknown"),
                            tier="unknown"
                        )
                except Exception as e:
                    logger.warning(f"[TokenTracker] Failed to record usage: {e}")

                return JSONResponse(
                    content=anthropic_response,
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

        if "anthropic-version" in original_headers:
            target_headers["anthropic-version"] = original_headers["anthropic-version"]

        if "anthropic-beta" in original_headers:
            target_headers["anthropic-beta"] = filter_beta_header(original_headers["anthropic-beta"], body_json.get('model', ''), "openrouter")

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
                    logger.error(f"[OpenRouter] Error: {redact_text(response.text)[:500]}")
                    return JSONResponse(
                        content=response.json(),
                        status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    )

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


async def proxy_to_custom(body_json: dict, original_headers: dict, endpoint: str, 
                        api_key: str = None, base_url: str = None) -> JSONResponse | StreamingResponse:
    """Proxy request to custom Anthropic-compatible API."""
    try:
        import os as _os
        # Use provided credentials or fallback to env vars (for backward compatibility)
        effective_base_url = base_url or CUSTOM_PROVIDER_BASE_URL
        effective_api_key = api_key or CUSTOM_PROVIDER_API_KEY

        base_url_str = effective_base_url.rstrip('/') if effective_base_url else ""
        skip_v1 = _os.getenv("CUSTOM_PROVIDER_SKIP_V1", "false").lower() == "true"

        if skip_v1:
            target_url = f"{base_url_str}/{endpoint}"
        else:
            target_url = f"{base_url_str}/v1/{endpoint}"

        target_headers = {
            "Content-Type": "application/json",
            "x-api-key": effective_api_key,
        }

        if "anthropic-version" in original_headers:
            target_headers["anthropic-version"] = original_headers["anthropic-version"]

        if "anthropic-beta" in original_headers:
            target_headers["anthropic-beta"] = filter_beta_header(original_headers["anthropic-beta"], body_json.get('model', ''), "custom")

        logger.info(f"[Custom] Sending to {target_url}")
        logger.info(f"[Custom] Model: {body_json.get('model')}")

        request_body = sanitize_for_custom(body_json)
        logger.info(f"[Custom] Request body size: {len(request_body)/1024:.1f}KB")

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            stream = body_json.get("stream", False)

            if stream:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Custom] Response status: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"[Custom] Error response: {response.text[:500]}")

                response_body = fix_streaming_tool_inputs(response.content)

                async def stream_response():
                    yield response_body

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
                    logger.error(f"[Custom] Error: {redact_text(response.text)[:500]}")
                    return JSONResponse(
                        content=response.json(),
                        status_code=response.status_code,
                        headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']},
                    )

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
