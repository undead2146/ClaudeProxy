#!/usr/bin/env python3
"""
Claude Code Proxy - Unified Router for GLM and Antigravity (Gemini)
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
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse, Response, HTMLResponse
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

# GLM Model mappings (when using GLM provider)
GLM_HAIKU_MODEL = os.getenv("GLM_HAIKU_MODEL", "glm-4.7")
GLM_SONNET_MODEL = os.getenv("GLM_SONNET_MODEL", "glm-4.7")
GLM_OPUS_MODEL = os.getenv("GLM_OPUS_MODEL", "glm-4.7")

# Antigravity configuration
ANTIGRAVITY_ENABLED = os.getenv("ANTIGRAVITY_ENABLED", "false").lower() == "true"
ANTIGRAVITY_PORT = int(os.getenv("ANTIGRAVITY_PORT", "8081"))
ANTIGRAVITY_BASE_URL = f"http://localhost:{ANTIGRAVITY_PORT}"
ANTIGRAVITY_CONFIG_DIR = os.getenv("ANTIGRAVITY_CONFIG_DIR", ".antigravity")

# Runtime configuration file
CONFIG_FILE = Path("config.json")

# Configuration lock for thread-safe updates
config_lock = threading.Lock()

# Runtime configuration (loaded from file or env vars)
runtime_config = {
    "sonnet_provider": os.getenv("SONNET_PROVIDER", "antigravity"),
    "haiku_provider": os.getenv("HAIKU_PROVIDER", "antigravity"),
    "opus_provider": os.getenv("OPUS_PROVIDER", "anthropic"),
    "sonnet_model": os.getenv("ANTIGRAVITY_SONNET_MODEL", "gemini-3-pro-high[1m]"),
    "haiku_model": os.getenv("ANTIGRAVITY_HAIKU_MODEL", "gemini-3-flash[1m]"),
    "opus_model": os.getenv("ANTIGRAVITY_OPUS_MODEL", "gemini-3-pro-high[1m]"),
    "last_updated": datetime.now().isoformat()
}

# In-memory log buffer (last 100 log entries)
from collections import deque
log_buffer = deque(maxlen=100)
log_buffer_lock = threading.Lock()

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

# In-memory log buffer (last 100 log entries)
from collections import deque
log_buffer = deque(maxlen=100)
log_buffer_lock = threading.Lock()

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
ANTIGRAVITY_SONNET_MODEL = os.getenv("ANTIGRAVITY_SONNET_MODEL", "gemini-3-pro-high[1m]")
ANTIGRAVITY_HAIKU_MODEL = os.getenv("ANTIGRAVITY_HAIKU_MODEL", "gemini-3-flash[1m]")
ANTIGRAVITY_OPUS_MODEL = os.getenv("ANTIGRAVITY_OPUS_MODEL", "gemini-3-pro-high[1m]")

# GitHub Copilot configuration (via copilot-api proxy)
ENABLE_COPILOT = os.getenv("ENABLE_COPILOT", "false").lower() == "true"
GITHUB_COPILOT_BASE_URL = os.getenv("GITHUB_COPILOT_BASE_URL", "http://localhost:4141")
GITHUB_COPILOT_SONNET_MODEL = os.getenv("GITHUB_COPILOT_SONNET_MODEL", "claude-sonnet-4.5")
GITHUB_COPILOT_HAIKU_MODEL = os.getenv("GITHUB_COPILOT_HAIKU_MODEL", "claude-haiku-4.5")
GITHUB_COPILOT_OPUS_MODEL = os.getenv("GITHUB_COPILOT_OPUS_MODEL", "claude-opus-4.5")

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
REQUEST_TIMEOUT = 300.0

# Antigravity process handle
antigravity_process = None

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

def get_provider_config(model: str) -> Tuple[Optional[str], Optional[str], str, str, str]:
    """Determine which provider to use based on model name.
    
    Returns: (api_key, base_url, tier, translated_model, provider_type)
    provider_type can be: 'glm', 'antigravity', 'anthropic', or 'unknown'
    """
    # Detect tier from model name
    tier = "Unknown"
    model_lower = model.lower()
    
    # First, check if model matches any configured model names
    if GLM_HAIKU_MODEL and model == GLM_HAIKU_MODEL:
        tier = "Haiku"
    elif GLM_SONNET_MODEL and model == GLM_SONNET_MODEL:
        tier = "Sonnet"
    elif GLM_OPUS_MODEL and model == GLM_OPUS_MODEL:
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
    # Check for GLM model patterns
    elif model_lower.startswith("glm-"):
        # Infer tier from GLM version number
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
            logger.info(f"[Proxy] Routing Sonnet → Antigravity ({sonnet_model})")
            return None, ANTIGRAVITY_BASE_URL, tier, sonnet_model, "antigravity"
        elif current_sonnet_provider == "glm" and GLM_SONNET_MODEL and SONNET_PROVIDER_BASE_URL:
            logger.info(f"[Proxy] Routing Sonnet → GLM ({GLM_SONNET_MODEL})")
            return SONNET_PROVIDER_API_KEY, SONNET_PROVIDER_BASE_URL, tier, GLM_SONNET_MODEL, "glm"
        elif current_sonnet_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Sonnet → GitHub Copilot ({sonnet_model})")
            return None, GITHUB_COPILOT_BASE_URL, tier, sonnet_model, "copilot"
        else:
            logger.info(f"[Proxy] Routing Sonnet → Anthropic (OAuth)")
            # For Anthropic, use a real Claude model name
            real_model = "claude-sonnet-4-5-20250929" if "glm" in model_lower or "gemini" in model_lower else model
            return None, None, tier, real_model, "anthropic"
    
    elif tier == "Haiku":
        if current_haiku_provider == "antigravity" and ANTIGRAVITY_ENABLED:
            logger.info(f"[Proxy] Routing Haiku → Antigravity ({haiku_model})")
            return None, ANTIGRAVITY_BASE_URL, tier, haiku_model, "antigravity"
        elif current_haiku_provider == "glm" and GLM_HAIKU_MODEL and HAIKU_PROVIDER_BASE_URL:
            logger.info(f"[Proxy] Routing Haiku → GLM ({GLM_HAIKU_MODEL})")
            return HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL, tier, GLM_HAIKU_MODEL, "glm"
        elif current_haiku_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Haiku → GitHub Copilot ({haiku_model})")
            return None, GITHUB_COPILOT_BASE_URL, tier, haiku_model, "copilot"
        else:
            logger.info(f"[Proxy] Routing Haiku → Anthropic (OAuth)")
            # For Anthropic, use a real Claude model name
            real_model = "claude-3-5-haiku-20241022" if "glm" in model_lower or "gemini" in model_lower else model
            return None, None, tier, real_model, "anthropic"
    
    elif tier == "Opus":
        if current_opus_provider == "antigravity" and ANTIGRAVITY_ENABLED:
            logger.info(f"[Proxy] Routing Opus → Antigravity ({opus_model})")
            return None, ANTIGRAVITY_BASE_URL, tier, opus_model, "antigravity"
        elif current_opus_provider == "glm" and GLM_OPUS_MODEL and OPUS_PROVIDER_BASE_URL:
            logger.info(f"[Proxy] Routing Opus → GLM ({GLM_OPUS_MODEL})")
            return OPUS_PROVIDER_API_KEY, OPUS_PROVIDER_BASE_URL, tier, GLM_OPUS_MODEL, "glm"
        elif current_opus_provider == "copilot" and ENABLE_COPILOT:
            logger.info(f"[Proxy] Routing Opus ? GitHub Copilot ({GITHUB_COPILOT_OPUS_MODEL})")
            return None, GITHUB_COPILOT_BASE_URL, tier, GITHUB_COPILOT_OPUS_MODEL, "copilot"
        else:
            logger.info(f"[Proxy] Routing Opus → Anthropic (OAuth)")
            # For Anthropic, use a real Claude model name
            real_model = "claude-opus-4-20250514" if "glm" in model_lower or "gemini" in model_lower else model
            return None, None, tier, real_model, "anthropic"
    
    # Unknown model - try to infer or default to Anthropic
    logger.warning(f"[Proxy] Unknown model tier for '{model}', defaulting to Haiku tier")
    # Default to Haiku routing
    current_haiku_provider = get_haiku_provider()
    if current_haiku_provider == "antigravity" and ANTIGRAVITY_ENABLED:
        return None, ANTIGRAVITY_BASE_URL, "Haiku", ANTIGRAVITY_HAIKU_MODEL, "antigravity"
    elif current_haiku_provider == "glm" and GLM_HAIKU_MODEL and HAIKU_PROVIDER_BASE_URL:
        return HAIKU_PROVIDER_API_KEY, HAIKU_PROVIDER_BASE_URL, "Haiku", GLM_HAIKU_MODEL, "glm"
    elif current_haiku_provider == "copilot" and ENABLE_COPILOT:
        return None, GITHUB_COPILOT_BASE_URL, "Haiku", haiku_model, "copilot"
    else:
        return None, None, "Unknown", "claude-3-5-haiku-20241022", "anthropic"

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
                    headers=dict(response.headers),
                    media_type="text/event-stream",
                )
            else:
                response = await client.post(target_url, headers=target_headers, content=request_body)
                logger.info(f"[Antigravity] Response status: {response.status_code}")
                
                if response.status_code >= 400:
                    error_text = response.text[:500]
                    logger.error(f"[Antigravity] Error response: {error_text}")
                
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                    headers=dict(response.headers),
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
                    headers=dict(response.headers),
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
                        headers=dict(response.headers),
                    )
                
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
    
    except httpx.TimeoutException:
        logger.error(f"[Copilot] Timeout after {REQUEST_TIMEOUT}s")
        return JSONResponse(content={
            "error": "GitHub Copilot API timeout"
        }, status_code=504)
    except Exception as e:
        logger.error(f"[Copilot] Error: {type(e).__name__}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


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
        
        # Route to GLM provider
        elif api_key and base_url and provider_type == "glm":
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
            "glm": {
                "haiku": {"model": GLM_HAIKU_MODEL, "provider_set": bool(HAIKU_PROVIDER_BASE_URL)},
                "sonnet": {"uses_oauth": not bool(SONNET_PROVIDER_API_KEY), "oauth_token_available": get_oauth_token() is not None},
            },
            "antigravity": {
                "enabled": ANTIGRAVITY_ENABLED,
                "status": antigravity_status,
                "port": ANTIGRAVITY_PORT,
                "models": {
                    "sonnet": ANTIGRAVITY_SONNET_MODEL if SONNET_PROVIDER == "antigravity" else None,
                    "haiku": ANTIGRAVITY_HAIKU_MODEL if HAIKU_PROVIDER == "antigravity" else None,
                    "opus": ANTIGRAVITY_OPUS_MODEL if OPUS_PROVIDER == "antigravity" else None,
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
    
    # Add provider availability info
    providers_available = {
        "antigravity": ANTIGRAVITY_ENABLED,
        "glm": bool(GLM_HAIKU_MODEL or GLM_SONNET_MODEL or GLM_OPUS_MODEL),
        "anthropic": get_oauth_token() is not None,
        "copilot": ENABLE_COPILOT
    }
    
    # Available models per provider
    available_models = {
        "antigravity": [
            "gemini-3-pro-high",
            "gemini-3-pro-high[1m]",
            "gemini-3-pro-low",
            "gemini-3-pro-low[1m]",
            "gemini-3-flash",
            "gemini-3-flash[1m]",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
            "claude-sonnet-4-5",
            "claude-sonnet-4-5[1m]",
            "claude-opus-4-5",
            "claude-opus-4-5[1m]"
        ],
        "glm": ["glm-4.7"],
        "anthropic": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-3-5-haiku-20241022",
            "claude-opus-4-20250514"
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
        ]
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
        valid_providers = ["antigravity", "glm", "anthropic", "copilot"]
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
    usage_html_path = os.path.join(os.path.dirname(__file__), 'usage.html')
    if os.path.exists(usage_html_path):
        with open(usage_html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return HTMLResponse(content=html)
    else:
        return HTMLResponse(content="<html><body><h1>Usage page not found</h1></body></html>", status_code=404)


async def test_antigravity_endpoint(request: Request):
    """Test Antigravity with a minimal request."""
    try:
        test_body = {
            "model": "gemini-3-flash[1m]",
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


routes = [
    Route("/v1/messages", messages_endpoint, methods=["POST"]),
    Route("/v1/messages/count_tokens", count_tokens_endpoint, methods=["POST"]),
    Route("/health", health_check, methods=["GET"]),
    Route("/config", get_config_endpoint, methods=["GET"]),
    Route("/config", update_config_endpoint, methods=["POST"]),
    Route("/logs", get_logs_endpoint, methods=["GET"]),
    Route("/logs/clear", clear_logs_endpoint, methods=["POST"]),
    Route("/logs.html", logs_page_endpoint, methods=["GET"]),
    Route("/usage", usage_page_endpoint, methods=["GET"]),
    Route("/test-antigravity", test_antigravity_endpoint, methods=["GET"]),
    Route("/dashboard", dashboard_endpoint, methods=["GET"]),
    Route("/", dashboard_endpoint, methods=["GET"]),
]

app = Starlette(debug=True, routes=routes)

if __name__ == "__main__":
    import uvicorn
    import atexit
    import signal

    # Load configuration from file
    load_config()

    logger.info("=" * 70)
    logger.info("Claude Code Proxy - Unified Router (GLM + Gemini + Anthropic + Copilot)")
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
        elif provider == "glm":
            model_map = {
                "Sonnet": GLM_SONNET_MODEL or "not configured",
                "Haiku": GLM_HAIKU_MODEL or "not configured",
                "Opus": GLM_OPUS_MODEL or "not configured"
            }
            return f"GLM ({model_map.get(tier, 'unknown')})"
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
    
    logger.info("=" * 70)
    logger.info("Proxy listening on http://0.0.0.0:8082")
    logger.info("Configuration Dashboard: http://localhost:8082/dashboard")
    logger.info("Health check: http://localhost:8082/health")
    logger.info("API endpoint: http://localhost:8082/v1/messages")
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
        uvicorn.run(app, host="0.0.0.0", port=8082, log_level="info")
    finally:
        cleanup()


