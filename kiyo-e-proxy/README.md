# @kiyo-e/claude-code-proxy for EnowDev

This directory contains the configuration for the **Node.js/TypeScript proxy** (@kiyo-e/claude-code-proxy) to connect Claude Code to EnowDev's API.

## Quick Start

### 1. Install Node.js (if not already installed)
Download from: https://nodejs.org/ (v16 or higher)

### 2. Check Installation
```powershell
node --version
npm --version
```

### 3. Configure Claude Code
```powershell
.\CONFIGURE-CLAUDE.ps1
```

### 4. Start the Proxy
```powershell
.\START-PROXY.ps1
```

### 5. Test the Connection
```powershell
.\TEST-PROXY.ps1
```

## Files in This Directory

- **`.env`** - Configuration file with API credentials and model mappings
- **`START-PROXY.ps1`** - Script to start the proxy with debug mode
- **`CONFIGURE-CLAUDE.ps1`** - Script to configure Claude Code settings
- **`TEST-PROXY.ps1`** - Script to test the proxy connection
- **`SETUP-INSTRUCTIONS.md`** - Detailed setup and troubleshooting guide
- **`README.md`** - This file

## What is @kiyo-e/claude-code-proxy?

It's a Node.js/TypeScript proxy that:
- Translates between Anthropic API format and OpenAI API format
- Allows Claude Code to connect to OpenAI-compatible APIs
- Supports model name mapping via environment variables

## Configuration Overview

### API Credentials (.env)
```env
OPENAI_API_BASE=https://api.enowdev.id
OPENAI_API_KEY=enx_d3ed82a62392b104d02b7b732daa2a44496671063b33d22e1e4c1869446fecab
PORT=8080
```

### Model Mappings (.env)
```env
CLAUDE_37_SONNET=claude-3.7-sonnet
CLAUDE_SONNET_45=claude-sonnet-4.5
CLAUDE_HAIKU_45=claude-haiku-4.5
```

### Claude Code Settings (%USERPROFILE%\.claude\settings.json)
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8080",
    "ANTHROPIC_API_KEY": "dummy-key-not-used"
  }
}
```

## Critical Issue: /v1 Path

**Problem**: The proxy may append `/v1/chat/completions` to the base URL, but EnowDev does NOT use the `/v1` path.

-  Correct: `https://api.enowdev.id/messages`
-  Wrong: `https://api.enowdev.id/v1/messages` (returns 404)

**What to Check**:
1. Start the proxy in debug mode
2. Look at the logs to see what URL is being called
3. If you see `/v1` in the URL, this is the problem

**Solutions**:
1. Check if the proxy supports `OPENAI_API_PATH` configuration
2. Use a reverse proxy (nginx/Caddy) to rewrite URLs
3. Use the Python proxy instead (already supports `SKIP_V1`)

## Installation Options

### Option 1: Use with npx (No Installation)
```powershell
npx @kiyo-e/claude-code-proxy
```

### Option 2: Global Installation
```powershell
npm install -g @kiyo-e/claude-code-proxy
claude-code-proxy
```

## Verification Steps

### 1. Check Proxy is Running
```powershell
curl http://localhost:8080/health
```

### 2. Check Proxy Logs
Look for:
- Incoming Anthropic API format requests
- Model name translation (claude-3-7-sonnet  claude-3.7-sonnet)
- Outgoing OpenAI API format requests
- URL being called (check for /v1 issue)

### 3. Test with Claude Code
Just use Claude Code normally - all requests will go through the proxy.

## Troubleshooting

### 404 Errors
- **Cause**: Proxy is appending `/v1` to the URL
- **Solution**: See "Critical Issue: /v1 Path" section above

### Model Name Errors
- **Cause**: Model mapping not working
- **Solution**: Check .env file has correct mappings

### Connection Refused
- **Cause**: Proxy not running or firewall blocking
- **Solution**: Check proxy is running, check firewall settings

### Thinking Models Not Working
- **Cause**: Proxy may not handle `thinking` parameter correctly
- **Solution**: Check if proxy appends `-thinking` to model names

## Alternative: Python Proxy

If you encounter issues with the Node.js proxy, the Python proxy in the parent directory is already configured and tested with EnowDev:

```powershell
cd ..
python proxy.py
```

See: `C:\tools\claude-code-proxy\ENOWDEV-SETUP.md`

## Support

For detailed instructions and troubleshooting, see:
- **SETUP-INSTRUCTIONS.md** - Complete setup guide
- **Parent directory** - Python proxy alternative

## Summary

 **Configuration Created**: .env file with EnowDev credentials  
 **Known Issue**: /v1 path may cause 404 errors  
 **Alternative**: Python proxy already supports EnowDev  
 **Ready to Test**: Run START-PROXY.ps1 and check logs  
