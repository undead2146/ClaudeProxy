# Claude Code Proxy: Weekly Rate Limits? Resolved!

Route **each Claude Code model tier** to **different providers**! Use free **Gemini 3** models through **Antigravity**, direct **Anthropic API**, **GitHub Copilot** access, or **Z.AI** models - all at the same time through one unified proxy with zero-downtime switching via web dashboard.

## Why This Exists

Apparently I'm one of the "2%" of users that should encounter or be affected by Anthropic's new weekly limits. So I built this proxy to route certain models to LLM providers of your choice - welcome to the good ol days when we didn't need to worry about hitting our weekly limit. These models work with agents too!

## 🚀 Quick Start

**Windows (PowerShell):**
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Antigravity globally (for free Gemini access)
npm install -g antigravity-claude-proxy@latest

# 3. Start proxy & dashboard
cd scripts
.\manage-proxy.ps1 start

# 4. Configure Claude Code CLI
$env:ANTHROPIC_BASE_URL = "http://localhost:8082"

# 5. Open dashboard to configure routing
# Browser: http://localhost:8082/dashboard
```

## 📊 Web Dashboard

**Main Dashboard:** http://localhost:8082/dashboard  
**Proxy Logs:** http://localhost:8082/logs.html  
**Antigravity Dashboard:** http://localhost:8081 (when running)  
**Health Check:** http://localhost:8082/health

### Dashboard Features
- **Live Provider Status** - See which providers are configured and available.
- **Model Selection** - Choose specific models for Sonnet, Haiku, and Opus tiers.
- **Instant Updates** - Changes apply immediately without restart.
- **Per-Tier Routing** - Route each Claude tier to different providers/models.

## Key Features

- ✨ **4+ Providers** - Antigravity (Gemini), Z.AI, Anthropic, GitHub Copilot.
- 🔄 **Dynamic Switching** - Change providers/models without restart via web dashboard.
- 💰 **Cost Optimized** - Use free Gemini for heavy tasks, keep Claude for premium needs.
- 🔐 **OAuth Preserved** - Keep your Claude subscription active for Sonnet/Opus.
- 🎯 **Dead Simple** - Unified management script for all services.
- 🌐 **Network Ready** - Accessible from other PCs on your local network.

## What It Does

```
Claude Code CLI         Proxy (8082) Routes To
─────────────────       ────────────────────────────────
Haiku  (tier)      ──▶  Antigravity (Gemini 3 Flash)
Sonnet (tier)      ──▶  Anthropic Direct (Official API)
Opus   (tier)      ──▶  GitHub Copilot (Claude 3.5 Opus)
```

## 🎯 Provider Setup

### Antigravity (Free Gemini/Claude Models)

Antigravity proxies Claude API calls to Google's Gemini models through their AI Studio infrastructure.

**Setup:**
```powershell
# Install globally
npm install -g antigravity-claude-proxy@latest

# Start proxy, then visit http://localhost:8081
# Click "Add Account" and sign in with Google
```

**Features:**
- ✅ Free Gemini 3 Flash, Pro models.
- ✅ Claude models via Gemini API translation.
- ✅ Multiple account support.

### Anthropic Direct API

Use official Anthropic API with your API key.

**Setup:**
- Add `ANTHROPIC_API_KEY=sk-ant-xxx` to your `.env` file.

### GitHub Copilot

Use Claude models through your GitHub Copilot subscription.

**Setup:**
- Add `GITHUB_COPILOT_API_KEY=ghu_xxx` to your `.env` file.

### Z.AI (Zhipu)

Fast Chinese language models from Zhipu AI.

**Setup:**
- Add `ZAI_API_KEY=your-key` to your `.env` file.

## 🛠️ Management Commands

All operations are handled via the unified `manage-proxy.ps1` script in the `scripts/` folder.

| Command | Description |
|---------|-------------|
| `.\manage-proxy.ps1 start` | Start both Antigravity and the main proxy. |
| `.\manage-proxy.ps1 stop` | Stop all proxy-related processes. |
| `.\manage-proxy.ps1 restart` | Cold restart of all services. |
| `.\manage-proxy.ps1 status` | Show health status of all ports/services. |

## 🏗️ Windows Production Setup

### 1. Network Access (Multi-PC)

The proxy is configured to listen on `0.0.0.0` (all interfaces). To allow other PCs to use it:

**Add Firewall Rule (Admin Required):**
```powershell
.\scripts\setup-firewall.ps1
```

**Find Server IP:**
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" }
```

### 2. Client PC Setup

On another PC on the same network:

1. **Configure Environment:**
```powershell
$env:ANTHROPIC_BASE_URL = "http://SERVER_IP:8082"
```

2. **Update Settings:**
Edit `%USERPROFILE%\.claude\settings.json`:
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://SERVER_IP:8082"
  }
}
```

### 3. Auto-Start on Boot

To have the proxy start automatically when Windows boots (regardless of login):

**Install Task (Admin Required):**
```powershell
.\scripts\install-autostart.ps1
```

## 📡 API Endpoint Support

| Endpoint | Support | Notes |
|----------|---------|-------|
| `POST /v1/messages` | ✅ Full | Main chat completion endpoint. |
| `POST /v1/messages/count_tokens` | ✅ Full | Works with Anthropic/Copilot; emulated for others. |
| `GET /v1/models` | ✅ Full | Returns list of available models for current provider. |
| `GET /health` | ✅ Full | Proxy status endpoint. |

## 🔧 Troubleshooting

### "Max retries exceeded" / 429 Errors
This happens when Google accounts hit rate limits from too many requests.
- **Solution:** Add more Google accounts to Antigravity to distribute the load.

### Account Marked "Unhealthy"
If an account hits too many rate limits, Antigravity marks it unhealthy.
- **Solution:** 
  1. Delete `C:\Users\USER\.config\antigravity-proxy\accounts.json`.
  2. Restart proxy: `.\manage-proxy.ps1 restart`.
  3. Re-add account at http://localhost:8081.

### Proxy Not Intercepting
Verify `ANTHROPIC_BASE_URL` is set correctly:
```powershell
echo $env:ANTHROPIC_BASE_URL  # Should be http://localhost:8082
```

## 🔐 Security Considerations

1. **Local Network Only:** The firewall script restricts access to the local subnet. Do not expose port 8082 to the public internet.
2. **OAuth Tokens:** Tokens are stored locally on the server. Never share your `accounts.json` or `credentials.json`.
3. **No Auth:** The proxy does not have built-in password protection; it relies on network-level security.

## 📄 License

MIT

---
*Built to keep the 2% coding.*
