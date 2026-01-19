#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Stops the Claude Code Proxy server.

.DESCRIPTION
    This script gracefully stops the running proxy server by reading the PID file
    and terminating the process.

.EXAMPLE
    .\stop-proxy.ps1
    Stops the running proxy server.
#>

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Define paths
$ProxyRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProxyRoot "logs"
$PidFile = Join-Path $LogDir "proxy.pid"

# Check if PID file exists
if (-not (Test-Path $PidFile)) {
    Write-Host "Proxy is not running (PID file not found)" -ForegroundColor Yellow
    exit 0
}

# Read PID
$proxyPid = Get-Content $PidFile -ErrorAction SilentlyContinue
if (-not $proxyPid) {
    Write-Host "ERROR: PID file is empty or invalid" -ForegroundColor Red
    Remove-Item $PidFile -Force
    exit 1
}

# Check if process exists
$process = Get-Process -Id $proxyPid -ErrorAction SilentlyContinue

if (-not $process) {
    Write-Host "Proxy process (PID: $proxyPid) is not running" -ForegroundColor Yellow
    Remove-Item $PidFile -Force
    exit 0
}

# Verify it's a Python process
if ($process.ProcessName -ne "python") {
    Write-Host "WARNING: Process $proxyPid is not a Python process (it's $($process.ProcessName))" -ForegroundColor Yellow
    if (-not $Force) {
        Write-Host "Use -Force to kill it anyway" -ForegroundColor Yellow
        exit 1
    }
}

# Stop the process
Write-Host "Stopping Claude Code Proxy (PID: $proxyPid)..." -ForegroundColor Cyan

try {
    if ($Force) {
        # Force kill
        Stop-Process -Id $proxyPid -Force
        Write-Host "Proxy forcefully stopped" -ForegroundColor Yellow
    } else {
        # Graceful stop
        Stop-Process -Id $proxyPid
        Write-Host "Proxy stopped gracefully" -ForegroundColor Green
    }

    # Wait for process to exit
    $timeout = 10
    $elapsed = 0
    while ((Get-Process -Id $proxyPid -ErrorAction SilentlyContinue) -and ($elapsed -lt $timeout)) {
        Start-Sleep -Milliseconds 500
        $elapsed += 0.5
    }

    if (Get-Process -Id $proxyPid -ErrorAction SilentlyContinue) {
        Write-Host "WARNING: Process did not stop within $timeout seconds" -ForegroundColor Yellow
        if (-not $Force) {
            Write-Host "Try running with -Force flag" -ForegroundColor Yellow
        }
    }

} catch {
    Write-Host "ERROR: Failed to stop process: $_" -ForegroundColor Red
    exit 1
}

# Remove PID file
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue

Write-Host "Proxy stopped successfully" -ForegroundColor Green
