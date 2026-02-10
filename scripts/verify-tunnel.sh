#!/bin/bash
# Final Verification Script - Run this before deploying to VPS

echo "========================================"
echo "CLOUDFLARE TUNNEL - FINAL VERIFICATION"
echo "========================================"
echo ""

# Check if tunnel is running
if pgrep -f cloudflared > /dev/null 2>&1 || tasklist 2>/dev/null | grep -q cloudflared; then
    echo " Cloudflared is running"
else
    echo " Cloudflared is NOT running"
    exit 1
fi

# Check if proxy is running
if curl -s http://localhost:8082/health > /dev/null 2>&1; then
    echo " Proxy server is responding"
else
    echo " Proxy server is NOT responding"
    exit 1
fi

# Get tunnel URL
if [ -f "TUNNEL_URL.txt" ]; then
    TUNNEL_URL=$(cat TUNNEL_URL.txt)
    echo " Tunnel URL found: $TUNNEL_URL"
else
    echo " TUNNEL_URL.txt not found"
    exit 1
fi

# Test tunnel health endpoint
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$TUNNEL_URL/health" 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo " Tunnel health check passed (HTTP $HTTP_CODE)"
else
    echo " Tunnel health check failed (HTTP $HTTP_CODE)"
    exit 1
fi

# Test API endpoint
API_RESPONSE=$(curl -s -X POST "$TUNNEL_URL/v1/messages" \
    -H "Content-Type: application/json" \
    -H "anthropic-version: 2023-06-01" \
    -d '{"model":"claude-sonnet-4-5-20250929","messages":[{"role":"user","content":"test"}],"max_tokens":5}' 2>/dev/null)

if echo "$API_RESPONSE" | grep -q '"type":"message"'; then
    echo " API endpoint is working"
else
    echo " API endpoint test failed"
    exit 1
fi

# Check git status
if git diff-index --quiet HEAD -- 2>/dev/null; then
    echo " All changes committed"
else
    echo " Uncommitted changes detected"
fi

# Check if ahead of origin
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null)
if [ "$AHEAD" -gt 0 ]; then
    echo " $AHEAD commit(s) ready to push"
else
    echo " Repository is up to date"
fi

echo ""
echo "========================================"
echo " ALL CHECKS PASSED"
echo "========================================"
echo ""
echo "Tunnel URL: $TUNNEL_URL"
echo ""
echo "Ready for VPS deployment!"
echo ""
