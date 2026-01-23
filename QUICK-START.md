# Claude Code Proxy - Quick Start Guide

## ONE COMMAND TO RULE THEM ALL

### Start Everything:
`powershell
cd c:\tools\claude-code-proxy\scripts
.\manage-proxy.ps1 start
`

This single command starts:
- Antigravity server (port 8081)
- Main proxy server (port 8082)

### Stop Everything:
`powershell
.\manage-proxy.ps1 stop
`

### Check Status:
`powershell
.\manage-proxy.ps1 status
`

### Restart Everything:
`powershell
.\manage-proxy.ps1 restart
`

## AUTO-START ON BOOT (Already Installed!)

The auto-start task is now configured. Both services will automatically start when your PC boots.

**Management:**
- View task: `Get-ScheduledTask -TaskName 'Claude Code Proxy Auto-Start'`
- Disable: `.\install-autostart.ps1 -Uninstall`
- Re-install: `.\install-autostart.ps1`

## Access Points

- **Antigravity Dashboard**: http://localhost:8081
- **Main Proxy Dashboard**: http://localhost:8082/dashboard
- **Logs Viewer**: http://localhost:8082/logs.html

## First Time Setup

1. Open http://localhost:8081 (Antigravity dashboard)
2. Go to Accounts tab
3. Click "Add Account"
4. Complete Google OAuth authorization
5. Verify account shows as healthy

That's it! Everything will work automatically after reboot.
