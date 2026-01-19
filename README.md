# Claude Code Proxy: Weekly Rate Limits? Resolved!

Route **each Claude Code model tier** to **different providers**! Use [GLM](https://z.ai/subscribe?ic=CAO6LGU9S1) for Haiku/Opus and keep Sonnet on your [Claude](https://claude.ai/) subscription - all at the same time.

## Why This Exists

Apparently I'm one of the "2%" of users that should encounter or be affected by Anthropic's new weekly limits. So I built this proxy to route certain models to LLM providers of your choice - welcome to the good ol days when we didn't need to worry about hitting our weekly limit. These models work with agents too!

## Key Features

- ✨ **3 independent providers** - Route Haiku, Opus, and Sonnet to different APIs simultaneously
- 🔄 **Mix and match** - GLM for speed/cost, Claude for premium
- 💰 **Cost optimized** - Route cheap tasks to alternatives, premium to Claude
- 🔐 **OAuth preserved** - Keep your Claude subscription active for Sonnet
- 🎯 **Dead simple** - Each tier configured with just 2 environment variables
- 🌐 **Cross-platform** - Works on macOS, Linux, and Windows

## What It Does

```
Claude Code UI          Proxy Routes To
─────────────────       ───────────────────────────────
Haiku  (glm-4.7)        → GLM API
Opus   (claude-opus)    → Real Anthropic (OAuth)
Sonnet (claude-sonnet)  → Real Anthropic (OAuth)
```

## How It Works

The proxy intercepts Claude Code's API requests:

1. **You set:** `ANTHROPIC_BASE_URL=http://localhost:8082`
2. **Claude Code sends requests to:** `localhost:8082` instead of `api.anthropic.com`
3. **Proxy checks model name:**
   - `glm-4.7` → Routes to GLM (HAIKU_PROVIDER_BASE_URL)
   - `claude-opus-4-5` → Routes to real Anthropic (OAuth passthrough)
   - `claude-sonnet-4-5` → Routes to real Anthropic (OAuth passthrough)

## Quick Start

**macOS/Linux:**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure providers - Create .env file with:
cat > .env << 'EOF'
# Provider configurations
HAIKU_PROVIDER_API_KEY=sk-glm-xxx
HAIKU_PROVIDER_BASE_URL=https://api.z.ai/api/anthropic

# Opus and Sonnet use OAuth (leave commented)
# OPUS_PROVIDER_API_KEY=
# OPUS_PROVIDER_BASE_URL=
# SONNET_PROVIDER_API_KEY=
# SONNET_PROVIDER_BASE_URL=

# Model name configuration
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.7
EOF

# 3. Configure Claude Code (add to ~/.zshrc or ~/.bashrc)
export ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.7
export ANTHROPIC_BASE_URL=http://localhost:8082  # ⚠️ CRITICAL

# 4. Start proxy & use Claude Code
python proxy.py &
claude
```

**Windows (PowerShell):**
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure providers - Create .env file with:
@"
# Provider configurations
HAIKU_PROVIDER_API_KEY=sk-glm-xxx
HAIKU_PROVIDER_BASE_URL=https://api.z.ai/api/anthropic

# Opus and Sonnet use OAuth (leave commented)
# OPUS_PROVIDER_API_KEY=
# OPUS_PROVIDER_BASE_URL=
# SONNET_PROVIDER_API_KEY=
# SONNET_PROVIDER_BASE_URL=

# Model name configuration
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.7
"@ | Out-File -FilePath .env -Encoding utf8

# 3. Configure Claude Code (add to PowerShell $PROFILE)
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "glm-4.7"
$env:ANTHROPIC_BASE_URL = "http://localhost:8082"  # ⚠️ CRITICAL

# 4. Start proxy & use Claude Code
Start-Process python -ArgumentList "proxy.py" -WindowStyle Hidden
claude
```

**What goes where:**
- **`.env` file** → Provider configs + model name mappings (read by proxy)
- **Shell env vars** → Model names (`ANTHROPIC_DEFAULT_*_MODEL`) + base URL pointing to localhost:8082

## Supported Providers

- **[GLM](https://z.ai/subscribe?ic=CAO6LGU9S1)** (via Z.AI) - Fast, cheap Chinese models
- **[Claude](https://claude.ai/)** - Premium Anthropic models via OAuth
- **Any Anthropic-compatible API** - Works with any provider supporting `/v1/messages`

## Use Cases

```bash
Haiku  → GLM (glm-4.7)   # Cheap, fast
Opus   → Claude (real)   # Quality, your subscription
Sonnet → Claude (real)   # Your subscription
```

## Benefits

| Benefit | Description |
|---------|-------------|
| ✅ **Keep your Claude subscription** | Uses OAuth, no API key needed |
| ✅ **3 providers simultaneously** | Different provider for each tier |
| ✅ **Native Claude Code support** | Uses built-in environment variables |
| ✅ **Update-proof** | No SDK modifications, survives updates |
| ✅ **Transparent** | `/model` command shows actual routed model names |
| ✅ **Simple** | Just environment variables, no complex config |

## Requirements

- Python 3.8+
- Claude Code installed globally
- Provider(s) with Anthropic-compatible API

## Using with Agents

Agents automatically use your configured models:

```yaml
---
name: my-agent
model: haiku  # Uses glm-4.7 (your ANTHROPIC_DEFAULT_HAIKU_MODEL)
---
```

## API Endpoint Support

The proxy implements the following Anthropic API endpoints:

| Endpoint | GLM Providers | Real Anthropic | Notes |
|----------|--------------|----------------|-------|
| `POST /v1/messages` | ✅ Full support | ✅ Full support | Main chat completion endpoint |
| `POST /v1/messages/count_tokens` | ⚠️ Returns 501 | ✅ Full support | Token counting before sending. GLM doesn't support this - use token counts from message responses instead |
| `GET /health` | ✅ Proxy health | ✅ Proxy health | Proxy status endpoint (not forwarded to providers) |

**About Token Counting:**
- **Sonnet (Real Anthropic)**: Token counting works normally via `/v1/messages/count_tokens`
- **Haiku/Opus (GLM)**: Token counting returns HTTP 501 with a helpful message. Token usage is still available in every `/v1/messages` response under the `usage` field.

## Troubleshooting

**Proxy not intercepting requests?**

macOS/Linux:
```bash
echo $ANTHROPIC_BASE_URL  # Should output: http://localhost:8082
echo $ANTHROPIC_DEFAULT_HAIKU_MODEL  # Should output: glm-4.7
# If empty, add to ~/.zshrc or ~/.bashrc:
# export ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.7
# export ANTHROPIC_BASE_URL=http://localhost:8082
```

Windows:
```powershell
echo $env:ANTHROPIC_BASE_URL  # Should output: http://localhost:8082
echo $env:ANTHROPIC_DEFAULT_HAIKU_MODEL  # Should output: glm-4.7
# If empty, add to PowerShell $PROFILE:
# $env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "glm-4.7"
# $env:ANTHROPIC_BASE_URL = "http://localhost:8082"
```

**Check if proxy is running:**
```bash
curl http://localhost:8082/health
```

Expected response:
```json
{
  "status": "healthy",
  "haiku": {"model": "glm-4.7", "provider_set": true},
  "opus": {"uses_oauth": true},
  "sonnet": {"uses_oauth": true}
}
```

**Models not routing correctly?**
- Verify model names in `.env` match `ANTHROPIC_DEFAULT_*_MODEL` vars
- Check proxy logs for routing info
- Test provider API keys directly with `curl`

**Sonnet OAuth not working?**
```bash
claude --login  # Refresh your Claude session
```

## Windows Production Setup

This section covers setting up the proxy for production use on Windows, including:
- Auto-start at system boot (works without user login)
- Network access for multiple PCs
- Firewall configuration
- Client PC setup

### Prerequisites

- Windows 11 (or Windows 10)
- Python 3.11+ installed and in PATH
- Administrator rights
- Claude Pro subscription (for OAuth)
- Z.AI API key (for Haiku routing)

### Installation Steps

#### 1. Install Python Dependencies

```powershell
cd C:\tools\claude-code-proxy
pip install -r requirements.txt
```

#### 2. Configure Environment Variables

Copy `.env.example` to `.env` and edit with your actual values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Minimum required configuration:
```env
HAIKU_PROVIDER_API_KEY=your_actual_zai_api_key
HAIKU_PROVIDER_BASE_URL=https://api.z.ai/api/anthropic
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.7
```

Leave SONNET provider blank to use OAuth (reads from `%USERPROFILE%\.claude\.credentials.json`).

#### 3. Configure Claude Code

Edit your Claude Code settings at: `%USERPROFILE%\.claude\settings.json`

```json
{
  "env": {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7",
    "ANTHROPIC_SMALL_FAST_MODEL": "glm-4.7",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8082"
  },
  "autoUpdatesChannel": "latest"
}
```

**Important:** Use `127.0.0.1` for localhost on the server PC. Client PCs will use your network IP (see below).

#### 4. Test Manual Start

Before setting up auto-start, verify the proxy works manually:

```powershell
.\scripts\start-proxy.ps1
```

Wait a few seconds, then test:

```powershell
.\scripts\test-proxy.ps1
```

Check status:

```powershell
.\scripts\status-proxy.ps1
```

Stop the proxy:

```powershell
.\scripts\stop-proxy.ps1
```

### Auto-Start Configuration (System Startup)

The proxy can start automatically when Windows boots, **regardless of whether you log in**.

#### Install Auto-Start Task

Run as Administrator:

```powershell
.\scripts\install-autostart.ps1
```

This creates a Windows Task Scheduler task that:
- Starts at system startup (not user logon)
- Runs whether you're logged in or not
- Auto-restarts on failure (up to 3 times)
- Loads environment variables from `.env`
- Logs to `logs\proxy.log`

#### Verify Auto-Start

After installation, the proxy should start automatically. Check status:

```powershell
Get-ScheduledTask -TaskName "Claude Code Proxy Auto-Start"
```

To manually start/stop the task:

```powershell
# Start
Start-ScheduledTask -TaskName "Claude Code Proxy Auto-Start"

# Stop
Stop-ScheduledTask -TaskName "Claude Code Proxy Auto-Start"

# Uninstall
.\scripts\install-autostart.ps1 -Uninstall
```

### Network Access Setup

To access the proxy from other computers on your network (e.g., 192.168.1.x):

#### 1. Proxy Configuration (Already Done)

The proxy is already configured to listen on `0.0.0.0` (all network interfaces) in `proxy.py:322`.

#### 2. Windows Firewall Configuration

Run as Administrator:

```powershell
# Add firewall rule for port 8082
New-NetFirewallRule -DisplayName "Claude Code Proxy" `
    -Direction Inbound `
    -LocalPort 8082 `
    -Protocol TCP `
    -Action Allow `
    -Profile Private `
    -RemoteAddress LocalSubnet
```

**Security Notes:**
- `-Profile Private` restricts to private networks only
- `-RemoteAddress LocalSubnet` restricts to local network (192.168.x.x, 10.x.x.x)
- For home networks, this is sufficient
- For production, consider additional authentication

#### 3. Find Your Server IP Address

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" }
```

Example output: `192.168.1.16`

#### 4. Test Network Access

From the same PC (server):

```powershell
curl http://192.168.1.16:8082/health
```

From another PC on the network:

```powershell
curl http://192.168.1.16:8082/health
```

Expected response:
```json
{
  "status": "healthy",
  "haiku": {"model": "glm-4.7", "provider_set": true},
  "sonnet": {"uses_oauth": true, "oauth_token_available": true}
}
```

### Client PC Setup

To configure another Windows PC to use the proxy on your network:

#### 1. Install Claude Code

Download and install from: https://claude.ai/claude-code

#### 2. Authenticate with Claude Pro

```powershell
claude --login
```

**Important:** Each PC needs its own OAuth login. The token is personal and stored locally.

#### 3. Configure Claude Code Settings

Edit `%USERPROFILE%\.claude\settings.json` on the **client PC**:

```json
{
  "env": {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7",
    "ANTHROPIC_SMALL_FAST_MODEL": "glm-4.7",
    "ANTHROPIC_BASE_URL": "http://192.168.1.16:8082"
  },
  "autoUpdatesChannel": "latest"
}
```

**Replace** `192.168.1.16` with your actual proxy server IP address.

#### 4. Test Client Connection

From the client PC:

```powershell
# Test connectivity
curl http://192.168.1.16:8082/health

# Test Claude Code
claude "test message with haiku"  # Should route to Z.AI via proxy
```

### File Structure

```
C:\tools\claude-code-proxy\
├── proxy.py                    # Main proxy server (runs on 0.0.0.0:8082)
├── .env                        # Your configuration (not in git)
├── .env.example                # Configuration template
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── scripts\
│   ├── start-proxy.ps1        # Start proxy manually
│   ├── stop-proxy.ps1         # Stop proxy
│   ├── status-proxy.ps1       # Check proxy status
│   ├── test-proxy.ps1         # Run health tests
│   └── install-autostart.ps1  # Setup auto-start at boot
└── logs\
    └── proxy.log              # Runtime logs (auto-created)
```

### Management Scripts

All scripts are in the `scripts\` directory:

| Script | Purpose |
|--------|---------|
| `start-proxy.ps1` | Start proxy manually (requires admin) |
| `stop-proxy.ps1` | Stop running proxy |
| `status-proxy.ps1` | Show detailed proxy status |
| `test-proxy.ps1` | Run comprehensive health checks |
| `install-autostart.ps1` | Install/uninstall auto-start task |

### Troubleshooting

#### Proxy Not Starting

1. Check if Python is in PATH:
   ```powershell
   python --version
   ```

2. Check logs:
   ```powershell
   Get-Content .\logs\proxy.log -Tail 50
   ```

3. Verify .env file exists and has correct values:
   ```powershell
   Get-Content .env
   ```

#### OAuth Token Not Found

The proxy reads the OAuth token from `%USERPROFILE%\.claude\.credentials.json`.

Check if token exists:

```powershell
$creds = Get-Content "$env:USERPROFILE\.claude\.credentials.json" | ConvertFrom-Json
$creds.claudeAiOauth.accessToken
```

If empty or missing:
1. Run `claude --login` to re-authenticate
2. Verify you have an active Claude Pro subscription
3. The token is personal - each PC needs its own login

#### Network Access Not Working

1. Verify firewall rule:
   ```powershell
   Get-NetFirewallRule -DisplayName "Claude Code Proxy"
   ```

2. Check if proxy is listening on network interface:
   ```powershell
   Get-NetTCPConnection -LocalPort 8082
   ```
   Should show `0.0.0.0:8082` or `[::]:8082`

3. Test from client PC:
   ```powershell
   Test-NetConnection -ComputerName 192.168.1.16 -Port 8082
   ```

4. Verify proxy.py is using `host="0.0.0.0"` (line 322)

#### Client PC Can't Connect

1. Check server IP is correct:
   ```powershell
   # On server PC
   Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" }
   ```

2. Verify firewall on server PC allows port 8082

3. Check client's `settings.json` has correct IP:
   ```powershell
   Get-Content "$env:USERPROFILE\.claude\settings.json"
   ```

4. Test connectivity:
   ```powershell
   curl http://192.168.1.16:8082/health
   ```

#### Auto-Start Not Working

1. Check task scheduler:
   ```powershell
   Get-ScheduledTask -TaskName "Claude Code Proxy Auto-Start"
   ```

2. View task history:
   ```powershell
   Get-ScheduledTaskInfo -TaskName "Claude Code Proxy Auto-Start"
   ```

3. Check logs after reboot:
   ```powershell
   Get-Content .\logs\proxy.log -Tail 100
   ```

4. Manually run the task to test:
   ```powershell
   Start-ScheduledTask -TaskName "Claude Code Proxy Auto-Start"
   ```

#### Thinking Block Errors

The proxy automatically filters problematic thinking blocks. If you see errors:

1. Check proxy logs for `[Filter]` messages
2. Verify `anthropic-beta` header filtering is working
3. Update Claude Code to latest version

### Configuration Examples

#### Example 1: Haiku to Z.AI, Opus/Sonnet to Anthropic (Recommended)

**.env:**
```env
HAIKU_PROVIDER_API_KEY=your_zai_api_key
HAIKU_PROVIDER_BASE_URL=https://api.z.ai/api/anthropic
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.7

# Sonnet uses OAuth - leave blank
```

**settings.json:**
```json
{
  "env": {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7",
    "ANTHROPIC_SMALL_FAST_MODEL": "glm-4.7",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8082"
  }
}
```

**Result:**
- Haiku requests → Z.AI (cheap, fast)
- Opus requests → Anthropic OAuth (premium, your subscription)
- Sonnet requests → Anthropic OAuth (your subscription)

#### Example 2: All to Z.AI (No Claude Subscription)

**.env:**
```env
HAIKU_PROVIDER_API_KEY=your_zai_api_key
HAIKU_PROVIDER_BASE_URL=https://api.z.ai/api/anthropic
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.7

SONNET_PROVIDER_API_KEY=your_zai_api_key
SONNET_PROVIDER_BASE_URL=https://api.z.ai/api/anthropic

OPUS_PROVIDER_API_KEY=your_zai_api_key
OPUS_PROVIDER_BASE_URL=https://api.z.ai/api/anthropic
ANTHROPIC_DEFAULT_OPUS_MODEL=glm-4.5-air
```

**Result:**
- All requests → Z.AI
- No Claude Pro subscription needed

### Testing Checklist

After setup, verify:

- [ ] Proxy starts manually with `.\scripts\start-proxy.ps1`
- [ ] Health check passes: `curl http://localhost:8082/health`
- [ ] Proxy accessible from network: `curl http://192.168.1.16:8082/health`
- [ ] Haiku requests route to Z.AI (check logs)
- [ ] Opus/Sonnet requests route to Anthropic OAuth (check logs)
- [ ] Auto-start task installed: `Get-ScheduledTask -TaskName "Claude Code Proxy Auto-Start"`
- [ ] Proxy starts after reboot (without login)
- [ ] Client PC can connect and use Claude Code
- [ ] Firewall allows local subnet: `Get-NetFirewallRule -DisplayName "Claude Code Proxy"`

### Security Considerations

1. **No Authentication:** The proxy has no built-in authentication. Only use on trusted networks.

2. **Firewall Configuration:** The default firewall rule restricts to local subnet. For additional security:
   ```powershell
   # Restrict to specific IP range
   New-NetFirewallRule -DisplayName "Claude Code Proxy" `
       -Direction Inbound `
       -LocalPort 8082 `
       -Protocol TCP `
       -Action Allow `
       -Profile Private `
       -RemoteAddress "192.168.1.0/24"
   ```

3. **OAuth Tokens:** Tokens are personal and stored locally. Never share credentials.json files.

4. **API Keys:** Store Z.AI API keys in `.env` only. Never commit to version control.

5. **Logs:** Proxy logs may contain sensitive data. Rotate and secure log files.

### Advanced Configuration

#### Custom Log Location

Edit `scripts\install-autostart.ps1` and change:
```powershell
$LogFile = Join-Path $LogDir "proxy.log"
```

#### Custom Port

Edit `proxy.py` line 322:
```python
uvicorn.run(app, host="0.0.0.0", port=8082, log_level="info")
```

Then update firewall rule and Claude Code settings accordingly.

#### Log Rotation

Create a scheduled task to rotate logs:

```powershell
# Create weekly log rotation task
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command `"Compress-Archive -Path 'C:\tools\claude-code-proxy\logs\proxy.log' -DestinationPath 'C:\tools\claude-code-proxy\logs\proxy_$(Get-Date -Format 'yyyy-MM-dd').zip'; Clear-Content 'C:\tools\claude-code-proxy\logs\proxy.log'`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3am
Register-ScheduledTask -TaskName "Claude Proxy Log Rotation" -Action $action -Trigger $trigger
```

## License

MIT

---