"""
Authentication middleware for Claude Code Proxy.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.config import PROXY_API_KEY


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check and favicon
        if request.url.path in ["/health", "/favicon.ico"]:
            return await call_next(request)

        # If no key is configured, allow all (Legacy/Insecure mode)
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
