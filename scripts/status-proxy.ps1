<#
.SYNOPSIS
    Checks the status of the Claude Code Proxy server.

.DESCRIPTION
    This script checks if the proxy server is running by reading the PID file
    and verifying the process exists and is responsive.

.EXAMPLE
    .\status-proxy.ps1
    Displays the current status of the proxy server.
#>

$ErrorActionPreference = "Stop"

# Define paths
$ProxyRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProxyRoot "logs"
$PidFile = Join-Path $LogDir "proxy.pid"
$LogFile = Join-Path $LogDir "proxy.log"

# ANSI color codes for better output
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Cyan = "`e[36m"
$Gray = "`e[90m"
$Reset = "`e[0m"

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Claude Code Proxy - Status Check" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Check if PID file exists
if (-not (Test-Path $PidFile)) {
    Write-Host "Status: ${Red}NOT RUNNING${Reset} (PID file not found)"
    Write-Host ""
    Write-Host "To start the proxy, run:" -ForegroundColor Yellow
    Write-Host "  .\scripts\start-proxy.ps1" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

# Read PID
$proxyPid = Get-Content $PidFile -ErrorAction SilentlyContinue
if (-not $proxyPid) {
    Write-Host "Status: ${Red}ERROR${Reset} (Invalid PID file)"
    Remove-Item $PidFile -Force
    exit 1
}

# Check if process exists
$process = Get-Process -Id $proxyPid -ErrorAction SilentlyContinue

if (-not $process) {
    Write-Host "Status: ${Red}NOT RUNNING${Reset} (Process $proxyPid not found)"
    Remove-Item $PidFile -Force
    Write-Host ""
    Write-Host "To start the proxy, run:" -ForegroundColor Yellow
    Write-Host "  .\scripts\start-proxy.ps1" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

# Process is running
Write-Host "Status: ${Green}RUNNING${Reset}"
Write-Host ""
Write-Host "Process Information:" -ForegroundColor Cyan
Write-Host "  PID:         $proxyPid" -ForegroundColor Gray
Write-Host "  Name:        $($process.ProcessName)" -ForegroundColor Gray
Write-Host "  Started:     $($process.StartTime)" -ForegroundColor Gray
Write-Host "  CPU Time:    $($process.CPU) seconds" -ForegroundColor Gray
Write-Host "  Memory:      $([math]::Round($process.WorkingSet64 / 1MB, 2)) MB" -ForegroundColor Gray

# Try to get network connections
try {
    $connections = Get-NetTCPConnection -OwningProcess $proxyPid -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq 8082 }
    if ($connections) {
        Write-Host ""
        Write-Host "Network Listening:" -ForegroundColor Cyan
        foreach ($conn in $connections) {
            $localAddr = $conn.LocalAddress
            if ($localAddr -eq "0.0.0.0") {
                $localAddr = "0.0.0.0 (all interfaces)"
            } elseif ($localAddr -eq "::") {
                $localAddr = ":: (all IPv6 interfaces)"
            }
            Write-Host "  $localAddr`:$($conn.LocalPort) - $($conn.State)" -ForegroundColor Gray
        }
    }
} catch {
    # Ignore errors getting network connections
}

# Check log file
if (Test-Path $LogFile) {
    $logInfo = Get-Item $LogFile
    Write-Host ""
    Write-Host "Log File:" -ForegroundColor Cyan
    Write-Host "  Path:        $LogFile" -ForegroundColor Gray
    Write-Host "  Size:        $([math]::Round($logInfo.Length / 1KB, 2)) KB" -ForegroundColor Gray
    Write-Host "  Modified:    $($logInfo.LastWriteTime)" -ForegroundColor Gray

    # Show last few log lines
    Write-Host ""
    Write-Host "Recent Log Entries (last 5 lines):" -ForegroundColor Cyan
    $lastLines = Get-Content $LogFile -Tail 5 -ErrorAction SilentlyContinue
    if ($lastLines) {
        foreach ($line in $lastLines) {
            Write-Host "  $line" -ForegroundColor DarkGray
        }
    }
}

# Test health endpoint
Write-Host ""
Write-Host "Health Check:" -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8082/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
    Write-Host "  ${Green}(OK)${Reset} Proxy is responding" -ForegroundColor Gray
    Write-Host "  Status:      $($response.status)" -ForegroundColor Gray

    if ($response.haiku) {
        $haikuProvider = "Anthropic"
        if ($response.haiku.provider_set) {
            $haikuProvider = "Z.AI"
        }
        Write-Host "  Haiku:       $($response.haiku.model) -> $haikuProvider" -ForegroundColor Gray
    }

    if ($response.sonnet) {
        $sonnetAuth = "API Key"
        if ($response.sonnet.uses_oauth) {
            $sonnetAuth = "OAuth"
        }

        $tokenStatus = "NOT FOUND"
        if ($response.sonnet.oauth_token_available) {
            $tokenStatus = "Available"
        }

        Write-Host "  Sonnet:      $sonnetAuth (Token: $tokenStatus)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ${Red}X${Reset} Health endpoint not responding" -ForegroundColor Yellow
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Management Commands:" -ForegroundColor Cyan
Write-Host "  .\scripts\test-proxy.ps1    - Run health tests" -ForegroundColor Gray
Write-Host "  .\scripts\restart-proxy.ps1 - Restart the proxy" -ForegroundColor Gray
Write-Host "  .\scripts\stop-proxy.ps1    - Stop the proxy" -ForegroundColor Gray
Write-Host "  Get-Content `"$LogFile`" -Tail 50 -Wait" -ForegroundColor Gray
Write-Host ""
