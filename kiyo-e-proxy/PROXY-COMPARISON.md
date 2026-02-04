# Proxy Comparison: Node.js vs Python for EnowDev

This document compares the two proxy options available for connecting Claude Code to EnowDev's API.

## Overview

| Feature | @kiyo-e/claude-code-proxy (Node.js) | proxy.py (Python) |
|---------|-------------------------------------|-------------------|
| **Language** | TypeScript/Node.js | Python |
| **Location** | `kiyo-e-proxy/` directory | Root directory |
| **Installation** | `npm install -g @kiyo-e/claude-code-proxy` | `pip install -r requirements.txt` |
| **Configuration** | `.env` in kiyo-e-proxy/ | `.env` in root |
| **Start Command** | `npx @kiyo-e/claude-code-proxy` | `python proxy.py` |
| **Port** | 8080 | 8080 |
| **Debug Mode** | `DEBUG=*` | Built-in logging |

## Critical Differences

### /v1 Path Handling

**Node.js Proxy:**
- Designed for OpenAI-compatible APIs
- May automatically append `/v1/chat/completions` to base URL
- **Unknown** if it supports skipping /v1
- **Risk**: May cause 404 errors with EnowDev

**Python Proxy:**
-  Supports `CUSTOM_PROVIDER_SKIP_V1=true`
-  Tested and working with EnowDev
-  Correctly calls `https://api.enowdev.id/messages`

### Model Name Mapping

**Node.js Proxy:**
- Uses environment variables (e.g., `CLAUDE_37_SONNET=claude-3.7-sonnet`)
- **Unknown** if it automatically translates model names
- May require manual configuration for each model

**Python Proxy:**
-  Built-in model name translation
-  Automatically handles hyphen  dot conversion
-  Works with all EnowDev models out of the box

### Thinking Models

**Node.js Proxy:**
- **Unknown** if it handles the `thinking` parameter
- May need to manually specify `-thinking` model names
- Requires testing

**Python Proxy:**
-  Automatically routes thinking models
-  Appends `-thinking` to model names when needed
-  Tested and working

## Setup Complexity

### Node.js Proxy

**Prerequisites:**
- Node.js v16+ installed
- npm installed
- Understanding of npm packages

**Setup Steps:**
1. Install Node.js (if not installed)
2. Create .env file with configuration
3. Install proxy: `npm install -g @kiyo-e/claude-code-proxy`
4. Configure Claude Code settings
5. Start proxy: `npx @kiyo-e/claude-code-proxy`
6. Test and troubleshoot /v1 path issue

**Estimated Time:** 10-30 minutes (depending on issues)

### Python Proxy

**Prerequisites:**
- Python 3.8+ installed
- pip installed

**Setup Steps:**
1. Install dependencies: `pip install -r requirements.txt`
2. .env file already configured
3. Configure Claude Code settings
4. Start proxy: `python proxy.py`

**Estimated Time:** 5 minutes

## Pros and Cons

### Node.js Proxy (@kiyo-e/claude-code-proxy)

**Pros:**
-  TypeScript/Node.js ecosystem
-  May have better performance (Node.js async I/O)
-  npm package management
-  Active development (potentially)

**Cons:**
-  Unknown EnowDev compatibility
-  /v1 path issue may require workarounds
-  Model mapping may not work automatically
-  Thinking models may not work
-  Requires Node.js installation
-  More complex troubleshooting

### Python Proxy (proxy.py)

**Pros:**
-  Tested and working with EnowDev
-  Supports `SKIP_V1` flag
-  Built-in model name translation
-  Thinking models work correctly
-  Simpler configuration
-  Already set up and ready to use
-  Detailed documentation (ENOWDEV-SETUP.md)

**Cons:**
-  Python dependency
-  May have slightly lower performance
-  Single-threaded (but sufficient for personal use)

## Recommendation

### Use Python Proxy If:
- You want a **proven, working solution**
- You need **quick setup** (5 minutes)
- You want to **avoid troubleshooting**
- You need **thinking models** to work
- You're okay with Python

### Use Node.js Proxy If:
- You **prefer Node.js/TypeScript**
- You want to **experiment** with the npm package
- You're willing to **troubleshoot** the /v1 path issue
- You have **time to test** and configure
- You need **Node.js ecosystem** integration

## Migration Between Proxies

Both proxies use the same Claude Code configuration, so you can easily switch:

### From Python to Node.js:
1. Stop Python proxy: `Ctrl+C`
2. Start Node.js proxy: `cd kiyo-e-proxy && .\START-PROXY.ps1`
3. Claude Code configuration stays the same (both use port 8080)

### From Node.js to Python:
1. Stop Node.js proxy: `Ctrl+C`
2. Start Python proxy: `cd .. && python proxy.py`
3. Claude Code configuration stays the same

## Testing Both Proxies

You can test both proxies to see which works better:

### Test Python Proxy:
```powershell
cd C:\tools\claude-code-proxy
python proxy.py
# In another window:
curl http://localhost:8080/health
```

### Test Node.js Proxy:
```powershell
cd C:\tools\claude-code-proxy\kiyo-e-proxy
.\START-PROXY.ps1
# In another window:
.\TEST-PROXY.ps1
```

## Performance Comparison

**Expected Performance:**
- Both proxies should have similar latency (< 10ms overhead)
- Network latency to EnowDev API is the bottleneck
- For personal use, performance difference is negligible

**Actual Performance:**
- Test both and measure response times
- Check CPU and memory usage
- Monitor for any connection issues

## Conclusion

**For most users, the Python proxy is recommended** because:
1.  It's already configured and tested with EnowDev
2.  It handles the /v1 path issue correctly
3.  It has built-in model name translation
4.  It supports thinking models
5.  It's ready to use in 5 minutes

**The Node.js proxy is an option if:**
1. You prefer the Node.js ecosystem
2. You're willing to troubleshoot potential issues
3. You want to experiment with the npm package

## Summary Table

| Criteria | Node.js Proxy | Python Proxy | Winner |
|----------|---------------|--------------|--------|
| Setup Time | 10-30 min | 5 min |  Python |
| EnowDev Compatibility | Unknown | Tested |  Python |
| /v1 Path Handling | Unknown | Supported |  Python |
| Model Mapping | Manual | Automatic |  Python |
| Thinking Models | Unknown | Working |  Python |
| Documentation | Basic | Detailed |  Python |
| Troubleshooting | Complex | Simple |  Python |
| Ecosystem | Node.js | Python | Preference |

**Overall Winner:**  **Python Proxy** (for EnowDev use case)

---

**Recommendation**: Start with the Python proxy. If you have specific reasons to use Node.js, try the Node.js proxy and fall back to Python if you encounter issues.
