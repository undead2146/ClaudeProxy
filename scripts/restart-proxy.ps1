<#
.SYNOPSIS
    Restarts the Claude Code Proxy server.

.DESCRIPTION
    This script stops the running proxy server (if any) and starts it again.

.EXAMPLE
    .\restart-proxy.ps1
#>

$ErrorActionPreference = "Stop"

# Use PSScriptRoot or current directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = $PWD }

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Claude Code Proxy - Restarting" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

# Stop the proxy
Write-Host "Stopping proxy..." -ForegroundColor Yellow
& "$ScriptDir\stop-proxy.ps1"

# Small delay
Start-Sleep -Seconds 1

# Start the proxy
Write-Host "Starting proxy..." -ForegroundColor Cyan
& "$ScriptDir\start-proxy.ps1"
