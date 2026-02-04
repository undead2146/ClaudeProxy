# Quick Start: @kiyo-e/claude-code-proxy with EnowDev

## Prerequisites Check

```powershell
# Check if Node.js is installed
node --version  # Should be v16 or higher

# Check if npm is installed
npm --version

# If not installed, download from: https://nodejs.org/
```

## Step 1: Configure Claude Code (30 seconds)

```powershell
cd C:\tools\claude-code-proxy\kiyo-e-proxy
.\CONFIGURE-CLAUDE.ps1
```

This creates `%USERPROFILE%\.claude\settings.json` with:
- ANTHROPIC_BASE_URL=http://localhost:8080
- ANTHROPIC_API_KEY=dummy-key-not-used

## Step 2: Start the Proxy (1 minute)

```powershell
.\START-PROXY.ps1
```

This will:
- Check if Node.js is installed
- Load configuration from .env
- Start the proxy with debug mode enabled
- Display logs in real-time

**What to look for in the logs:**
1.  Server started on port 8080
2.  Incoming requests from Claude Code
3.  Model name translation (claude-3-7-sonnet  claude-3.7-sonnet)
4.  Check URL being called (should NOT have /v1 in it)

## Step 3: Test the Connection (30 seconds)

Open a **new PowerShell window** and run:

```powershell
cd C:\tools\claude-code-proxy\kiyo-e-proxy
.\TEST-PROXY.ps1
```

This will:
- Check if proxy is running
- Send a test request
- Display the response
- Report any errors

## Step 4: Use Claude Code

Just start Claude Code normally - it will now use the proxy!

All requests will be routed through:
```
Claude Code  http://localhost:8080  https://api.enowdev.id
```

## Troubleshooting

### If you get 404 errors:

The proxy is likely appending `/v1` to the URL. Check the proxy logs to confirm.

**Quick fix**: Use the Python proxy instead:
```powershell
cd C:\tools\claude-code-proxy
python proxy.py
```

The Python proxy already supports `CUSTOM_PROVIDER_SKIP_V1=true` and works with EnowDev.

### If Node.js is not installed:

1. Download from: https://nodejs.org/
2. Install the LTS version
3. Restart PowerShell
4. Try again

### If the proxy won't start:

```powershell
# Try installing globally first
npm install -g @kiyo-e/claude-code-proxy

# Then run directly
claude-code-proxy
```

### If Claude Code doesn't use the proxy:

1. Check settings file exists:
   ```powershell
   cat $env:USERPROFILE\.claude\settings.json
   ```

2. Restart Claude Code

3. Check proxy logs to see if requests are coming in

## Configuration Files

All configuration is in this directory:

- **`.env`** - API credentials and model mappings
- **`%USERPROFILE%\.claude\settings.json`** - Claude Code configuration

## Next Steps

Once everything is working:

1. **Monitor the logs** to ensure requests are successful
2. **Check for /v1 path issues** (this is the most common problem)
3. **Test thinking models** to ensure they work correctly
4. **If issues persist**, use the Python proxy instead

## Getting Help

- **Detailed guide**: See SETUP-INSTRUCTIONS.md
- **Python proxy**: See ../ENOWDEV-SETUP.md
- **Logs**: Check the proxy output for error messages

## Summary

| Step | Command | Time |
|------|---------|------|
| 1. Configure Claude | `.\CONFIGURE-CLAUDE.ps1` | 30s |
| 2. Start Proxy | `.\START-PROXY.ps1` | 1m |
| 3. Test Connection | `.\TEST-PROXY.ps1` | 30s |
| 4. Use Claude Code | Just run it normally | - |

**Total setup time: ~2 minutes**

---

**Important**: Watch for the /v1 path issue in the logs. If you see it, use the Python proxy instead.
