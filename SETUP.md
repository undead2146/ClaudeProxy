# Setup Guide

## Quick Start (5 minutes)

1. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

2. Configure providers in .env (copy from .env.example)

3. Start the proxy:
   ```powershell
   .\scripts\manage-proxy.ps1 start
   ```

4. Configure Claude Code to point to the proxy:
   ```powershell
   $env:ANTHROPIC_BASE_URL = "http://localhost:8082"
   ```

## Provider Setup

### Antigravity (Gemini) - FREE
Already configured! Just set ANTIGRAVITY_ENABLED=true in .env

### Z.AI - Fast & Cheap
1. Get API key from https://z.ai/subscribe?ic=CAO6LGU9S1
2. Add to .env:
   ```
   HAIKU_PROVIDER_API_KEY=sk-zai-xxx
   HAIKU_PROVIDER_BASE_URL=https://api.z.ai/api/anthropic
   ```

### GitHub Copilot - Requires Adapter
Copilot uses OpenAI format, so you need:
- Use https://cope.duti.dev as proxy, OR
- Run https://github.com/acheong08/claude-copilot-proxy locally

Then set in .env:
```
GITHUB_COPILOT_API_KEY=your_token
GITHUB_COPILOT_BASE_URL=https://cope.duti.dev
```

## Security (REQUIRED for Sharing)

If you plan to expose this server (via Cloudflare Tunnel, ngrok, or public IP), you **MUST** configure an API Key to prevent unauthorized usage.

1. Open `.env` and set a secret key:
   ```properties
   PROXY_API_KEY=your-super-secret-password-here
   ```
2. Restart the proxy: `.\scripts\manage-proxy.ps1 restart`

### Connecting with Authentication
Clients must provide the key.

**Claude Code (Terminal):**
Add the key to the Base URL (easiest):
```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8082?key=your-secret-password"
```

**Dashboard:**
Open `http://localhost:8082/dashboard?key=your-secret-password`

## Configuration

### Switch Providers (No Restart!)

**Dashboard:** http://localhost:8082/dashboard

**Command Line:**
```powershell
.\scripts\switch-provider.ps1 -Tier sonnet -Provider antigravity
.\scripts\switch-provider.ps1 -Tier all -Provider zai
```

**Via SSH:**
```bash
ssh -L 8082:localhost:8082 user@server
# Then open http://localhost:8082/dashboard
```

**Edit config.json:**
```bash
ssh user@server
nano config.json  # Changes apply immediately
```

### Available Providers
- ntigravity - Gemini (free, high quality)
- zai - Zhipu Z.AI (fast, cheap)  
- nthropic - Official Claude (OAuth)
- copilot - GitHub Copilot (needs adapter)

### Example Configurations

**All Free:**
```json
{
  \"sonnet_provider\": \"antigravity\",
  \"haiku_provider\": \"antigravity\",
  \"opus_provider\": \"antigravity\"
}
```

**Mixed Performance:**
```json
{
  \"sonnet_provider\": \"antigravity\",
  \"haiku_provider\": \"glm\",
  \"opus_provider\": \"anthropic\"
}
```

See .env.example for all configuration options.
