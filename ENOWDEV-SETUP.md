# EnowDev API Setup Guide

This guide explains how to use the Claude Code Proxy with EnowDev's custom API endpoint.

## Configuration Summary

###  What Has Been Configured

1. **Environment Variables (.env)**
   - `CUSTOM_PROVIDER_API_KEY`: Your EnowDev API key
   - `CUSTOM_PROVIDER_BASE_URL`: https://api.enowdev.id
   - `CUSTOM_PROVIDER_SKIP_V1`: true (EnowDev doesn't use /v1 path)
   - `PORT`: 8080 (proxy listens on this port)
   - `SONNET_PROVIDER`: custom
   - `HAIKU_PROVIDER`: custom
   - `OPUS_PROVIDER`: custom

2. **Model Mappings**
   - Sonnet tier  `claude-sonnet-4.5`
   - Haiku tier  `claude-haiku-4.5`
   - Opus tier  `claude-opus-4.5`

3. **Proxy Code (proxy.py)**
   - Modified `proxy_to_custom()` function to support `CUSTOM_PROVIDER_SKIP_V1`
   - When enabled, URLs are constructed as: `https://api.enowdev.id/messages`
   - When disabled (default), URLs use: `https://api.enowdev.id/v1/messages`

## Available EnowDev Models

### Standard Models
- `claude-3.7-sonnet`
- `claude-sonnet-4`
- `claude-sonnet-4.5`
- `claude-haiku-4.5`

### Thinking Models (Separate Model Names)
- `claude-3.7-sonnet-thinking`
- `claude-sonnet-4-thinking`
- `claude-sonnet-4.5-thinking`

**Note**: EnowDev uses dots in version numbers (e.g., `claude-3.7-sonnet`) instead of hyphens. The proxy automatically handles model name translation.

## How to Start the Proxy

### 1. Install Dependencies (First Time Only)

```powershell
pip install -r requirements.txt
```

This installs:
- fastapi
- httpx
- uvicorn
- python-dotenv

### 2. Start the Proxy

**Standard Mode:**
```powershell
python proxy.py
```

**Debug Mode (Recommended for Testing):**
```powershell
# Set environment variable for debug logging
$env:PYTHONUNBUFFERED=1
python proxy.py
```

**Using Uvicorn Directly (More Control):**
```powershell
uvicorn proxy:app --host 0.0.0.0 --port 8080 --log-level info
```

The proxy will start on `http://localhost:8080`

### 3. Verify Proxy is Running

Open a new terminal and run:

```powershell
curl http://localhost:8080/health
```

You should see a JSON response with status information.

## Configure Claude Code CLI

To use the proxy with Claude Code, you need to configure it to point to your local proxy instead of Anthropic's API.

### Option 1: Environment Variables (Session-Based)

Set these in your PowerShell session:

```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8080"
$env:ANTHROPIC_API_KEY = "dummy-key-not-used"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
$env:API_TIMEOUT_MS = "3000000"
```

Then run Claude Code in the same session.

### Option 2: Settings File (Persistent)

Create or edit `%USERPROFILE%\.claude\settings.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8080",
    "ANTHROPIC_API_KEY": "dummy-key-not-used",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "API_TIMEOUT_MS": "3000000"
  }
}
```

**Note**: The `ANTHROPIC_API_KEY` value doesn't matter since the proxy uses the EnowDev key from .env

## Testing the Setup

### 1. Test with curl

```powershell
curl -X POST http://localhost:8080/v1/messages `
  -H "Content-Type: application/json" `
  -H "x-api-key: test" `
  -H "anthropic-version: 2023-06-01" `
  -d '{
    "model": "claude-sonnet-4.5",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ]
  }'
```

### 2. Check Proxy Logs

The proxy logs all requests. Look for lines like:

```
[Proxy] Incoming request for model: claude-sonnet-4.5
[Proxy] Routing Sonnet  Custom Provider (claude-sonnet-4.5)
[Custom] Sending to https://api.enowdev.id/messages
[Custom] Model: claude-sonnet-4.5
[Custom] Response status: 200
```

### 3. Test with Claude Code

Once configured, simply use Claude Code normally. All requests will be routed through the proxy to EnowDev.

## Troubleshooting

### 404 Errors from EnowDev

**Problem**: Getting 404 errors when making requests.

**Solution**: Verify that `CUSTOM_PROVIDER_SKIP_V1=true` is set in your .env file. EnowDev's API does NOT use the `/v1` path.

**Check the logs** to see what URL is being called:
-  Correct: `https://api.enowdev.id/messages`
-  Wrong: `https://api.enowdev.id/v1/messages`

### Model Name Issues

**Problem**: EnowDev returns errors about unknown models.

**Solution**: EnowDev uses specific model names. Update the model mappings in .env:

```env
CUSTOM_PROVIDER_SONNET_MODEL=claude-sonnet-4.5
CUSTOM_PROVIDER_HAIKU_MODEL=claude-haiku-4.5
CUSTOM_PROVIDER_OPUS_MODEL=claude-opus-4.5
```

For thinking models, the proxy automatically routes them based on the tier (sonnet/haiku/opus in the name).

### Proxy Not Starting

**Problem**: Python errors when starting proxy.

**Solutions**:
1. Check Python version: `python --version` (needs Python 3.8+)
2. Install dependencies: `pip install -r requirements.txt`
3. Check for syntax errors: `python -m py_compile proxy.py`

### Claude Code Not Using Proxy

**Problem**: Claude Code still connects to Anthropic directly.

**Solutions**:
1. Verify environment variables are set: `echo $env:ANTHROPIC_BASE_URL`
2. Check settings.json exists and is valid JSON
3. Restart Claude Code after changing settings
4. Check proxy is running: `curl http://localhost:8080/health`

### Timeout Errors

**Problem**: Requests timing out.

**Solutions**:
1. Increase timeout in .env (default is 300 seconds):
   ```env
   REQUEST_TIMEOUT=600
   ```
2. Set longer timeout in Claude Code:
   ```env
   API_TIMEOUT_MS=3000000
   ```

### Connection Refused

**Problem**: Cannot connect to localhost:8080

**Solutions**:
1. Check proxy is running: `netstat -an | findstr "8080"`
2. Check firewall isn't blocking port 8080
3. Try binding to 127.0.0.1 instead of 0.0.0.0

## Advanced Configuration

### Using Different Models for Different Tiers

You can route different Claude Code model tiers to different EnowDev models:

```env
# Use Sonnet 4.5 for Sonnet tier
CUSTOM_PROVIDER_SONNET_MODEL=claude-sonnet-4.5

# Use Haiku 4.5 for Haiku tier (faster, cheaper)
CUSTOM_PROVIDER_HAIKU_MODEL=claude-haiku-4.5

# Use Sonnet 4 for Opus tier
CUSTOM_PROVIDER_OPUS_MODEL=claude-sonnet-4
```

### Enabling Debug Logging

For detailed debugging, enable file logging in .env:

```env
CLAUDE_PROXY_LOG_FILE=logs/proxy.log
```

Then check the log file:
```powershell
Get-Content logs\proxy.log -Tail 50 -Wait
```

### Running on Different Port

Change the port in .env:

```env
PORT=8090
```

Then update Claude Code configuration:
```env
ANTHROPIC_BASE_URL=http://localhost:8090
```

### Network Access (Multiple PCs)

To allow other computers on your network to use the proxy:

1. Find your IP address:
   ```powershell
   ipconfig | findstr "IPv4"
   ```

2. Configure firewall (run as Administrator):
   ```powershell
   New-NetFirewallRule -DisplayName "Claude Code Proxy" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
   ```

3. On client PCs, set:
   ```env
   ANTHROPIC_BASE_URL=http://YOUR_IP:8080
   ```

## Configuration Files Reference

### .env (Main Configuration)
- Location: `C:\tools\claude-code-proxy\.env`
- Contains: API keys, provider settings, model mappings
- **Important**: Never commit this file to version control!

### proxy.py (Proxy Server)
- Location: `C:\tools\claude-code-proxy\proxy.py`
- Modified: `proxy_to_custom()` function to support SKIP_V1 flag

### config.json (Runtime Configuration)
- Location: `C:\tools\claude-code-proxy\config.json`
- Auto-generated: Stores current provider routing
- Can be modified via web dashboard (if enabled)

### settings.json (Claude Code Configuration)
- Location: `%USERPROFILE%\.claude\settings.json`
- Contains: Claude Code environment variables
- Create manually if it doesn't exist

## Support

If you encounter issues:

1. Check the proxy logs for error messages
2. Verify your .env configuration matches this guide
3. Test the EnowDev API directly with curl
4. Check that `CUSTOM_PROVIDER_SKIP_V1=true` is set

## Summary

 **Configured**: EnowDev API credentials and settings  
 **Modified**: proxy.py to support no-/v1 endpoints  
 **Ready**: Start proxy with `python proxy.py`  
 **Next**: Configure Claude Code to use `http://localhost:8080`  

The proxy is now ready to route all Claude Code requests to your EnowDev API endpoint!
