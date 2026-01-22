#!/usr/bin/env python3
"""
Claude Code Proxy - Adds thinking blocks with proper signatures
"""

import os
import sys
import json
import logging
import hashlib
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import httpx
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse
from starlette.requests import Request

load_dotenv()

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

ANTHROPIC_DEFAULT_HAIKU_MODEL = os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "glm-4.7")
ANTHROPIC_DEFAULT_OPUS_MODEL = os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "glm-4.5-air")

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
REQUEST_TIMEOUT = 300.0

def get_oauth_token():
    """Read OAuth token from Claude Code's credentials file."""
    try:
        creds_path = Path.home() / ".claude" / ".credentials.json"
        if not creds_path.exists():
            return None
        with open(creds_path, 'r') as f:
            creds = json.load(f)
        return creds.get("claudeAiOauth", {}).get("accessToken")
    except Exception as e:
        logger.error(f"[OAuth] Failed to read credentials: {e}")
        return None

def get_provider_config(model: str) -> Tuple[Optional[str], Optional[str], str, str]:
    """Determine which provider to use based on model name."""
    # Handle short model names used by subagents
    if model.lower() == "haiku":
        model = ANTHROPIC_DEFAULT_HAIKU_MODEL
        logger.info(f"[Proxy] Translating 'haiku' → '{model}'")
    elif model.lower() == "opus":
        model = ANTHROPIC_DEFAULT_OPUS_MODEL
        logger.info(f"[Proxy] Translating 'opus' → '{model}'")
    
    # Check which provider to use
    if model == ANTHROPIC_DEFAULT_HAIKU_MODEL:
        return HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL, "Haiku", model
    if model == ANTHROPIC_DEFAULT_OPUS_MODEL:
        return OPUS_PROVIDER_API_KEY, OPUS_PROVIDER_BASE_URL, "Opus", model
    
    # Check by tier name in model string
    model_lower = model.lower()
    if "sonnet" in model_lower:
        return SONNET_PROVIDER_API_KEY, SONNET_PROVIDER_BASE_URL, "Sonnet", model
    if "opus" in model_lower:
        return OPUS_PROVIDER_API_KEY, OPUS_PROVIDER_BASE_URL, "Opus", model
    if "haiku" in model_lower:
        return HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL, "Haiku", model
    
    # Default
    return None, None, "Unknown", model

def generate_signature(thinking_content: str) -> str:
    """Generate a valid signature for thinking block."""
    # Create a hash of the thinking content
    return hashlib.sha256(thinking_content.encode()).hexdigest()[:32]

def fix_thinking_blocks(body_json: dict, has_thinking_beta: bool, use_real_anthropic: bool = False) -> dict:
    """
    Pass through everything unchanged - let Anthropic handle it.
    """
    return body_json

def has_thinking_in_beta(beta_header: str) -> bool:
    """Check if thinking is enabled in beta features."""
    if not beta_header:
        return False
    
    thinking_keywords = ['thinking', 'extended-thinking', 'interleaved-thinking']
    features_lower = beta_header.lower()
    
    return any(keyword in features_lower for keyword in thinking_keywords)


async def proxy_request(request: Request, endpoint: str) -> JSONResponse | StreamingResponse:
    """Main proxy function with complete thinking block support."""
    try:
        body = await request.body()
        body_json = json.loads(body) if body else {}
        original_model = body_json.get("model", "claude-sonnet-4-5-20250929")
        
        logger.info(f"[Proxy] Incoming request for model: {original_model}")
        
        api_key, base_url, tier, translated_model = get_provider_config(original_model)
        
        # Update the model in the request body with translated name
        body_json["model"] = translated_model
        
        original_headers = dict(request.headers)
        use_real_anthropic = False  # Track if using Real Anthropic OAuth
        
        # Route to appropriate provider
        if api_key and base_url:
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
                
                return StreamingResponse(
                    stream_response(),
                    status_code=response.status_code,
                    headers=dict(response.headers),
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
                        headers=dict(response.headers),
                    )
                
                # Strip thinking blocks from response for Real Anthropic OAuth
                response_json = response.json()
                if use_real_anthropic and response_json.get("content"):
                    response_json["content"] = [
                        block for block in response_json["content"]
                        if not (isinstance(block, dict) and block.get("type") in ["thinking", "redacted_thinking"])
                    ]
                    logger.info(f"[Proxy] Stripped thinking blocks from response")
                
                return JSONResponse(
                    content=response_json,
                    status_code=response.status_code,
                    headers=dict(response.headers),
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
        
        api_key, base_url, tier, translated_model = get_provider_config(original_model)
        
        # Update the model in the request body
        body_json["model"] = translated_model
        
        if not api_key and not base_url:
            return await proxy_request(request, "messages/count_tokens")
        else:
            return JSONResponse(content={"error": "Not supported"}, status_code=501)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def health_check(request: Request):
    return JSONResponse(content={
        "status": "healthy",
        "haiku": {"model": ANTHROPIC_DEFAULT_HAIKU_MODEL, "provider_set": bool(HAIKU_PROVIDER_BASE_URL)},
        "sonnet": {"uses_oauth": not bool(SONNET_PROVIDER_API_KEY), "oauth_token_available": get_oauth_token() is not None},
    })


routes = [
    Route("/v1/messages", messages_endpoint, methods=["POST"]),
    Route("/v1/messages/count_tokens", count_tokens_endpoint, methods=["POST"]),
    Route("/health", health_check, methods=["GET"]),
]

app = Starlette(debug=True, routes=routes)

if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("Claude Code Proxy - With Signature Support")
    logger.info("=" * 60)
    logger.info(f"Haiku: {ANTHROPIC_DEFAULT_HAIKU_MODEL} -> {'Z.AI' if HAIKU_PROVIDER_BASE_URL else 'Anthropic'}")
    logger.info(f"Sonnet: -> {'API Key' if SONNET_PROVIDER_API_KEY else 'Anthropic OAuth'}")
    oauth_token = get_oauth_token()
    logger.info(f"OAuth: {'Available (OK)' if oauth_token else 'NOT FOUND'}")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8082, log_level="info")
