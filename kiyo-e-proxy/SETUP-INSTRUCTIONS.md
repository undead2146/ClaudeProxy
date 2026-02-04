# @kiyo-e/claude-code-proxy Setup Instructions for EnowDev

This guide covers setting up the **Node.js/TypeScript proxy** (@kiyo-e/claude-code-proxy) to connect Claude Code to EnowDev's API.

## Prerequisites

- Node.js (v16 or higher)
- npm (comes with Node.js)

Check if installed:
```powershell
node --version
npm --version
```

If not installed, download from: https://nodejs.org/

## Installation

### Option 1: Global Installation (Recommended)

```powershell
npm install -g @kiyo-e/claude-code-proxy
```

### Option 2: Use with npx (No Installation Required)

You can run the proxy directly with npx without installing:
```powershell
npx @kiyo-e/claude-code-proxy
```

## Configuration

### 1. Environment Variables (.env file)

The `.env` file in this directory (`C:\tools\claude-code-proxy\kiyo-e-proxy\.env`) contains all necessary configuration:

- **OPENAI_API_BASE**: EnowDev API endpoint (https://api.enowdev.id)
- **OPENAI_API_KEY**: Your EnowDev API key
- **PORT**: Proxy server port (8080)
- **Model Mappings**: Critical for translating between Claude Code and EnowDev model names

### 2. Model Name Mapping

**The Problem:**
- Claude Code uses hyphens: `claude-3-7-sonnet`, `claude-sonnet-4-5`
- EnowDev uses dots: `claude-3.7-sonnet`, `claude-sonnet-4.5`

**The Solution:**
The .env file contains mappings like:
```env
CLAUDE_37_SONNET=claude-3.7-sonnet
CLAUDE_SONNET_45=claude-sonnet-4.5
```

### 3. Thinking Models

EnowDev treats thinking models as separate model names:
- Standard: `claude-3.7-sonnet`
- Thinking: `claude-3.7-sonnet-thinking`

The proxy should automatically append `-thinking` when Claude Code sends the `thinking` parameter.

## Starting the Proxy

### From the kiyo-e-proxy directory:

```powershell
cd C:\tools\claude-code-proxy\kiyo-e-proxy
```

### Standard Mode:
```powershell
npx @kiyo-e/claude-code-proxy
```

### Debug Mode (Recommended for Testing):
```powershell
$env:DEBUG="*"
npx @kiyo-e/claude-code-proxy
```

### If Globally Installed:
```powershell
claude-code-proxy
```

The proxy will start on `http://localhost:8080`

## Configure Claude Code

### Option 1: Settings File (Recommended)

Create or edit: `%USERPROFILE%\.claude\settings.json`

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

**To create this file:**
```powershell
# Create directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude"

# Create settings file
@"
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8080",
    "ANTHROPIC_API_KEY": "dummy-key-not-used",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "API_TIMEOUT_MS": "3000000"
  }
}
"@ | Out-File -FilePath "$env:USERPROFILE\.claude\settings.json" -Encoding UTF8
```

### Option 2: Environment Variables (Session-Based)

```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8080"
$env:ANTHROPIC_API_KEY = "dummy-key-not-used"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
$env:API_TIMEOUT_MS = "3000000"
```

## Verification

### 1. Check Proxy is Running

```powershell
curl http://localhost:8080/health
```

Or:
```powershell
Invoke-WebRequest -Uri http://localhost:8080/health
```

### 2. Test with a Simple Request

```powershell
curl -X POST http://localhost:8080/v1/messages `
  -H "Content-Type: application/json" `
  -H "x-api-key: test" `
  -H "anthropic-version: 2023-06-01" `
  -d '{
    "model": "claude-3-7-sonnet",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "Say hello"}
    ]
  }'
```

### 3. Check Proxy Logs

When running in debug mode, you should see:
- **Incoming request**: Anthropic API format with model `claude-3-7-sonnet`
- **Model mapping**: Translation to `claude-3.7-sonnet`
- **Outgoing request**: OpenAI API format to EnowDev
- **Response**: Successful response from EnowDev

## Critical Issue: /v1 Path Problem

### The Problem

The @kiyo-e/claude-code-proxy is designed to work with OpenAI-compatible APIs, which typically use:
```
https://api.openai.com/v1/chat/completions
```

However, **EnowDev does NOT use the /v1 path**:
-  Correct: `https://api.enowdev.id/messages`
-  Wrong: `https://api.enowdev.id/v1/messages` (returns 404)

### Potential Solutions

#### Solution 1: Check Proxy Configuration

The proxy may support configuration to skip /v1. Check the proxy's documentation or source code for:
- `OPENAI_API_PATH` variable
- `SKIP_V1` flag
- Path configuration options

#### Solution 2: Modify Base URL (Workaround)

If the proxy always appends `/v1/chat/completions`, you might try:
```env
OPENAI_API_BASE=https://api.enowdev.id/../
```

This is a hack and may not work.

#### Solution 3: Use a Reverse Proxy

Set up nginx or Caddy to rewrite URLs:
```nginx
location /v1/messages {
    rewrite ^/v1/messages /messages break;
    proxy_pass https://api.enowdev.id;
}
```

#### Solution 4: Fork and Modify the Proxy

If the proxy doesn't support skipping /v1, you may need to:
1. Clone the @kiyo-e/claude-code-proxy repository
2. Modify the code to make the path configurable
3. Run your modified version

#### Solution 5: Use the Python Proxy Instead

The Python proxy in the parent directory (`C:\tools\claude-code-proxy\proxy.py`) already supports `CUSTOM_PROVIDER_SKIP_V1=true` and works with EnowDev.

## Troubleshooting

### 404 Errors

**Symptom**: Getting 404 errors from EnowDev

**Cause**: The proxy is appending `/v1` to the URL

**Solution**: 
1. Check proxy logs to see the exact URL being called
2. Look for configuration options to skip /v1
3. Consider using the Python proxy instead

### Model Name Errors

**Symptom**: EnowDev returns "model not found" errors

**Cause**: Model name mapping not working

**Solution**:
1. Verify .env file has correct mappings
2. Check proxy logs to see what model name is being sent
3. Ensure the proxy is loading the .env file from the correct location

### Proxy Not Starting

**Symptom**: Error when running npx command

**Solutions**:
1. Check Node.js version: `node --version` (needs v16+)
2. Clear npm cache: `npm cache clean --force`
3. Try installing globally: `npm install -g @kiyo-e/claude-code-proxy`

### Connection Refused

**Symptom**: Cannot connect to localhost:8080

**Solutions**:
1. Check proxy is running: `netstat -an | findstr "8080"`
2. Check firewall settings
3. Try a different port in .env

### Thinking Models Not Working

**Symptom**: Thinking mode doesn't work

**Cause**: The proxy may not handle the `thinking` parameter correctly

**Solution**:
1. Check if the proxy appends `-thinking` to model names
2. May need to modify the proxy code
3. Check EnowDev's API documentation for thinking model format

## Comparison: Node.js vs Python Proxy

| Feature | @kiyo-e/claude-code-proxy (Node.js) | proxy.py (Python) |
|---------|-------------------------------------|-------------------|
| Language | TypeScript/Node.js | Python |
| /v1 Path | May require workaround |  Supports SKIP_V1 |
| Model Mapping | Via env variables |  Built-in |
| Setup | npm install | pip install |
| Status | Unknown EnowDev compatibility |  Tested with EnowDev |

**Recommendation**: If you encounter issues with the Node.js proxy, the Python proxy is already configured and working with EnowDev.

## Next Steps

1. **Install Node.js** (if not already installed)
2. **Start the proxy** with debug mode
3. **Check the logs** to see if /v1 is being appended
4. **Test with curl** to verify connectivity
5. **Configure Claude Code** to use the proxy
6. **If /v1 issue occurs**, consider using the Python proxy instead

## Support Resources

- @kiyo-e/claude-code-proxy GitHub: Search for the package on GitHub
- EnowDev API Documentation: Check with your API provider
- Python Proxy (Alternative): `C:\tools\claude-code-proxy\ENOWDEV-SETUP.md`

## Summary

 **Configuration Created**: .env file with EnowDev credentials  
 **Known Issue**: /v1 path may cause 404 errors  
 **Alternative**: Python proxy already supports EnowDev  
 **Ready to Test**: Start proxy and check logs  
