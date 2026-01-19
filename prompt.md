# PROMPT FOR CLAUDE CODE AGENT: Complete Multi-Provider Proxy Setup

## Context
I have a working Claude Code proxy server (`proxy.py`) that routes different model tiers to different providers:
- **Haiku (glm-4.7)** → Z.AI API (cheap alternative)
- **Sonnet/Opus** → Real Anthropic via Claude Pro OAuth (reads token from `~/.claude/.credentials.json`)

The proxy works locally but I need to complete the setup for production use.

## Current Working Configuration

### Proxy Server Details
- **Location**: `C:\tools\claude-code-proxy\proxy.py`
- **Port**: 8082
- **Host**: Currently `127.0.0.1` (localhost only)
- **OAuth Token Source**: Reads from `%USERPROFILE%\.claude\.credentials.json` under `claudeAiOauth.accessToken`

### Claude Code Settings (`~/.claude/settings.json`)
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

### Environment Variables (set before starting proxy)
```powershell
$env:HAIKU_PROVIDER_API_KEY = "e2413af35fc24c4492a4c1ed79adffe6.UsyF7fNYNPGedtXU"
$env:HAIKU_PROVIDER_BASE_URL = "https://api.z.ai/api/anthropic"
# SONNET uses OAuth (no env vars needed)
```

## Requirements to Complete

### 1. Auto-Start Proxy on Windows Boot
**Goal**: Proxy server starts automatically when Windows boots, runs in background.

**Requirements**:
- Create Windows Service OR Task Scheduler task
- Proxy runs on system startup
- Environment variables preserved
- Logs to file (e.g., `C:\tools\claude-code-proxy\logs\proxy.log`)
- Auto-restart on failure
- Easy way to stop/start/check status

**Preferred Method**: Windows Task Scheduler (easier than service)

### 2. Network Access Configuration
**Goal**: Access proxy from other computers on local network (192.168.1.x).

**My Network**:
- Proxy server: `192.168.1.16` (Windows PC)
- Client PC: Another computer on same network
- Both can SSH to each other (verified working)

**Requirements**:
- Change proxy to listen on `0.0.0.0` instead of `127.0.0.1`
- Configure Windows Firewall to allow port 8082
- Test connectivity from remote machine
- Update client Claude Code settings to use `http://192.168.1.16:8082`

### 3. Client PC Setup
**Goal**: Configure another PC to use the proxy server on 192.168.1.16.

**Client Requirements**:
- Install Claude Code
- Authenticate with Claude Pro (separate login)
- Configure settings.json to point to `http://192.168.1.16:8082`
- Same model mappings (glm-4.7 for Haiku)
- Test both Haiku and Sonnet work through remote proxy

### 4. Comprehensive README.md
**Goal**: Document entire setup so I can recreate from scratch.

**README Must Include**:
1. **Problem Statement**: Why this proxy exists (rate limits, cost optimization)
2. **Architecture**: How routing works (Haiku→Z.AI, Sonnet→OAuth)
3. **Prerequisites**: Python, packages, Claude Pro subscription
4. **Installation Steps**:
   - Dependencies
   - Proxy setup
   - Environment variables
   - Claude Code configuration
5. **Auto-Start Setup**: Complete Task Scheduler instructions
6. **Network Setup**: Firewall rules, remote access configuration
7. **Client PC Setup**: Step-by-step for additional computers
8. **Troubleshooting**: Common issues and solutions
9. **File Locations**: Where everything lives on Windows
10. **Testing**: How to verify each component works

### 5. Critical Technical Details

#### OAuth Token Handling
- Token stored in `~/.claude/.credentials.json` as `claudeAiOauth.accessToken`
- Token length: ~108 characters
- Proxy must read this file (already implemented in `proxy.py`)
- Client PCs need their OWN OAuth tokens (separate logins)

#### Known Issues Already Fixed
- ✅ OAuth token was empty → Fixed by reading from `claudeAiOauth.accessToken`
- ✅ Thinking blocks caused 400 errors → Fixed by removing them from request body
- ✅ Beta features incompatible → Fixed by filtering `interleaved-thinking-2025-05-14`

#### Proxy Modifications Needed
Current `proxy.py` has:
```python
uvicorn.run(app, host="127.0.0.1", port=8082, log_level="info")
```

Needs to become:
```python
uvicorn.run(app, host="0.0.0.0", port=8082, log_level="info")
```

#### Security Considerations
- No authentication on proxy (local network only)
- Firewall should restrict to 192.168.1.x subnet
- OAuth tokens are personal (each PC needs own login)

## Specific Tasks for Agent

### Task 1: Create Windows Auto-Start Solution
Create a PowerShell script and Task Scheduler XML that:
1. Sets environment variables
2. Starts proxy in background
3. Redirects output to log file
4. Runs on system startup
5. Auto-restarts on failure
6. Includes management commands (start/stop/status)

### Task 2: Configure Network Access
Provide exact commands to:
1. Modify `proxy.py` to listen on all interfaces
2. Add Windows Firewall rule for port 8082
3. Test from remote machine using `curl` or similar
4. Document how to check if proxy is accessible

### Task 3: Create Client PC Setup Guide
Step-by-step instructions for setting up another Windows PC:
1. Install Claude Code
2. Authenticate (explain OAuth login process)
3. Configure settings.json with remote proxy URL
4. Set environment variables for model mappings
5. Test Haiku and Sonnet routing
6. Troubleshoot common connection issues

### Task 4: Write Complete README.md
Create professional README with:
- Clear problem/solution statement
- Architecture diagram (ASCII art is fine)
- Complete installation guide
- Network setup instructions
- Troubleshooting section with actual error messages
- File structure reference

### Task 5: Create Helper Scripts
Provide PowerShell scripts for:
- `start-proxy.ps1` - Start proxy with correct env vars
- `stop-proxy.ps1` - Stop proxy gracefully
- `status-proxy.ps1` - Check if proxy is running
- `test-proxy.ps1` - Verify proxy works (health check)
- `install-autostart.ps1` - Set up Task Scheduler

## Important Notes

### What's Already Working
- ✅ Proxy routes Haiku to Z.AI successfully
- ✅ Proxy routes Sonnet to Anthropic OAuth successfully
- ✅ OAuth token reading from credentials file
- ✅ Thinking block filtering
- ✅ Beta feature filtering
- ✅ Local testing (127.0.0.1) works perfectly

### What Needs to Be Done
- ❌ Auto-start on boot
- ❌ Network accessibility
- ❌ Remote client configuration
- ❌ Documentation
- ❌ Management scripts

### File Structure
```
C:\tools\claude-code-proxy\
├── proxy.py                    # Main proxy (already working)
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
├── README.md                   # To be created
├── scripts\
│   ├── start-proxy.ps1        # To be created
│   ├── stop-proxy.ps1         # To be created
│   ├── status-proxy.ps1       # To be created
│   ├── test-proxy.ps1         # To be created
│   └── install-autostart.ps1  # To be created
└── logs\
    └── proxy.log              # Runtime logs
```

### Testing Checklist
After completion, verify:
- [ ] Proxy starts on Windows boot
- [ ] Proxy accessible from 192.168.1.16:8082
- [ ] Health endpoint works: `curl http://192.168.1.16:8082/health`
- [ ] Haiku requests go to Z.AI (check logs)
- [ ] Sonnet requests go to Anthropic OAuth (check logs)
- [ ] Client PC can connect and route correctly
- [ ] Auto-restart works after crash
- [ ] Firewall allows only local subnet

## Expected Deliverables

1. **Modified `proxy.py`**: Change host to `0.0.0.0`
2. **README.md**: Complete setup documentation
3. **PowerShell Scripts**: All management scripts in `scripts/` folder
4. **Task Scheduler Setup**: Auto-start configuration
5. **Firewall Commands**: Exact PowerShell commands to run
6. **Client Configuration Guide**: Separate section in README
7. **Troubleshooting Guide**: Common issues with solutions

## Example Test Scenario

After setup is complete, this should work:

**Server PC (192.168.1.16)**:
```powershell
# Proxy is already running (auto-started)
curl http://localhost:8082/health
# Returns: {"status":"healthy","haiku":{"model":"glm-4.7","provider_set":true},...}
```

**Client PC (192.168.1.x)**:
```powershell
# Test connectivity
curl http://192.168.1.16:8082/health
# Should return same health check

# Test Claude Code
claude "test haiku"  # Routes to Z.AI through proxy
claude "test sonnet" # Routes to Anthropic OAuth through proxy
```

## Priority Order

1. **Network Access** (highest priority - needed for multi-PC)
2. **Auto-Start** (second - convenience)
3. **Management Scripts** (third - operations)
4. **Documentation** (fourth - maintenance)
5. **Client Setup** (fifth - deployment)

## Additional Context

- I'm comfortable with PowerShell and Windows administration
- I have admin rights on both PCs
- Network is trusted (home network, not public)
- Z.AI API key is already working
- Claude Pro subscription is active and authenticated
- Both PCs run Windows 11
- Python 3.11+ installed on both machines

Please create all necessary files, scripts, and documentation to complete this setup. Include exact commands and clear explanations. The README should be detailed enough that I can recreate this entire setup from scratch on a new machine without needing to remember anything.
