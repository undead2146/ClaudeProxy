import time
import json
import uuid
import asyncio
import logging
import threading
import httpx
from typing import Optional, Dict, Any, List
from pathlib import Path

from core.config import logger, GITHUB_CLIENT_ID, GITHUB_BASE_URL, GITHUB_API_BASE_URL, config_lock, runtime_config, save_config
from core.sanitize import redact_sensitive_info

class CopilotManager:
    """
    Manages GitHub Copilot authentication and token lifecycle.
    Ported logic from copilot-api-claude-code.
    """
    
    def __init__(self):
        self.client_id = GITHUB_CLIENT_ID
        self.scopes = "read:user"
        self.copilot_token_url = f"{GITHUB_API_BASE_URL}/copilot_internal/v2/token"
        self.device_code_url = f"{GITHUB_BASE_URL}/login/device/code"
        self.access_token_url = f"{GITHUB_BASE_URL}/login/oauth/access_token"
        
        # Versions for headers
        self.copilot_version = "0.35.0"
        self.vscode_version = "1.96.0"
        self.editor_plugin_version = f"copilot-chat/{self.copilot_version}"
        self.user_agent = f"GitHubCopilotChat/{self.copilot_version}"
        self.api_version = "2025-10-01"

    async def get_device_code(self) -> Dict[str, Any]:
        """Start the device code flow."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.device_code_url,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json={
                    "client_id": self.client_id,
                    "scope": self.scopes
                }
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"[Copilot] Started device flow: user_code={data.get('user_code')}")
            return data

    async def poll_for_token(self, device_code: str) -> Dict[str, Any]:
        """
        Poll for the GitHub access token.
        Returns a dict with 'status' and 'token' or 'error'.
        """
        headers = {
            "Accept": "application/json", 
            "Content-Type": "application/json",
            "User-Agent": self.user_agent
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.access_token_url,
                headers=headers,
                json={
                    "client_id": self.client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                }
            )
        
        logger.info(f"[Copilot] Poll response status: {response.status_code}")
        
        if not response.is_success:
            logger.error(f"[Copilot] Poll failed: {response.status_code} {response.text}")
            return {"status": "error", "error": response.text}
        
        data = response.json()
        logger.info(f"[Copilot] Poll data: {redact_sensitive_info(data)}")
            
        if "error" in data:
            error = data["error"]
            if error == "authorization_pending":
                return {"status": "pending"}
            elif error == "slow_down":
                return {"status": "slow_down", "interval": data.get("interval", 10)}
            elif error == "expired_token":
                return {"status": "expired"}
            elif error == "access_denied":
                return {"status": "denied"}
            else:
                return {"status": "error", "error": data.get("error_description", error)}
        
        if "access_token" in data:
            token = data["access_token"]
            logger.info(f"[Copilot] Successfully obtained GitHub token (starts with {token[:5]}...)")
            # Store the token
            with config_lock:
                runtime_config["copilot_github_token"] = token
                save_config()
            return {"status": "success", "token": token}
        
        return {"status": "pending"}

    async def get_copilot_token(self) -> Optional[str]:
        """
        Get a short-lived Copilot token using the GitHub access token.
        Handles caching and refresh.
        """
        github_token = runtime_config.get("copilot_github_token")
        if not github_token:
            return None
            
        # Check cache
        cached_token = runtime_config.get("copilot_access_token")
        expires_at = runtime_config.get("copilot_expires_at", 0)
        
        # If valid for at least 60 more seconds, use it
        if cached_token and expires_at > (time.time() + 60):
            return cached_token
            
        # Fetch new token
        try:
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/json",
                "editor-version": f"vscode/{self.vscode_version}",
                "editor-plugin-version": self.editor_plugin_version,
                "user-agent": self.user_agent,
                "x-github-api-version": self.api_version,
                "x-vscode-user-agent-library-version": "electron-fetch"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(self.copilot_token_url, headers=headers)
                
                if response.status_code == 401:
                    logger.warning("[Copilot] GitHub token expired or revoked")
                    with config_lock:
                        runtime_config["copilot_github_token"] = None
                        save_config()
                    return None
                    
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"[Copilot] Successfully got short-lived Copilot token. Expires at {data.get('expires_at')}")
            
            new_token = data["token"]
            new_expires_at = data["expires_at"] # Usually a timestamp in seconds
            
            with config_lock:
                runtime_config["copilot_access_token"] = new_token
                runtime_config["copilot_expires_at"] = int(new_expires_at)
                save_config()
                
            return new_token
        except Exception as e:
            logger.error(f"[Copilot] Failed to get Copilot token: {e}")
            return None

    def get_headers(self, token: str, vision: bool = False, initiator: str = "user", session_id: Optional[str] = None) -> Dict[str, str]:
        """Construct headers for a Copilot API request."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "copilot-integration-id": "vscode-chat",
            "editor-version": f"vscode/{self.vscode_version}",
            "editor-plugin-version": self.editor_plugin_version,
            "user-agent": self.user_agent,
            "openai-intent": "conversation-agent",
            "x-github-api-version": self.api_version,
            "x-request-id": str(uuid.uuid4()),
            "x-vscode-user-agent-library-version": "electron-fetch",
        }
        
        if vision:
            headers["copilot-vision-request"] = "true"
            
        if initiator == "agent":
            headers["x-initiator"] = "agent"
            headers["x-interaction-type"] = "conversation-subagent"
        
        if session_id:
            headers["x-interaction-id"] = session_id
            
        return headers

    async def get_valid_models(self) -> List[str]:
        """Fetch the list of models supported by this Copilot account."""
        token = await self.get_copilot_token()
        if not token:
            return []
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GITHUB_COPILOT_API_URL}/models",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "User-Agent": self.user_agent,
                        "x-github-api-version": self.api_version
                    }
                )
                if response.is_success:
                    data = response.json()
                    # data is often a list of dictionaries with 'id'
                    if isinstance(data, list):
                        return [m.get("id") for m in data if m.get("id")]
                    elif isinstance(data, dict) and "data" in data:
                        return [m.get("id") for m in data["data"] if m.get("id")]
                return []
        except Exception as e:
            logger.error(f"[Copilot] Failed to fetch valid models: {e}")
            return []

    def map_model(self, model_id: str) -> str:
        """
        Map a requested model ID to a valid Copilot model ID.
        If it contains 'sonnet', use claude-3.5-sonnet.
        If it contains 'gpt-4' or 'opus', use gpt-4o.
        Fallback to gpt-4o.
        """
        m = model_id.lower()
        if "sonnet" in m:
            return "claude-3.5-sonnet"
        if "gpt-4o" in m:
            return "gpt-4o"
        if "gpt-4" in m or "opus" in m:
            return "gpt-4o"
        if "gemini" in m:
            if "flash" in m:
                return "gemini-1.5-flash"
            return "gemini-1.5-pro"
        
        return "gpt-4o" # Safe default for most Copilot accounts

# Singleton instance
copilot_manager = CopilotManager()
