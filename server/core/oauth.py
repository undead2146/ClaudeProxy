"""
OAuth token management for Anthropic API access.
"""

import json
import threading
from pathlib import Path
from datetime import datetime

import httpx

from core.config import logger

# OAuth refresh lock to prevent concurrent refresh attempts
oauth_refresh_lock = threading.Lock()

# OAuth refresh rate limiting to prevent retry loops
_last_oauth_refresh_failure = 0
_OAUTH_REFRESH_COOLDOWN = 60  # seconds


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

            if not refresh_token:
                logger.error("[OAuth] No refresh token available")
                return None

            with oauth_refresh_lock:
                # Re-read credentials after acquiring lock
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
                    return oauth_data.get("accessToken")

                try:
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

                        oauth_data["accessToken"] = new_token_data.get("access_token")
                        oauth_data["expiresAt"] = current_time_ms + (new_token_data.get("expires_in", 3600) * 1000)

                        if "refresh_token" in new_token_data:
                            oauth_data["refreshToken"] = new_token_data["refresh_token"]

                        creds["claudeAiOauth"] = oauth_data
                        with open(creds_path, 'w') as f:
                            json.dump(creds, f, indent=2)

                        logger.info("[OAuth] Token refreshed successfully")
                        _last_oauth_refresh_failure = 0
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
