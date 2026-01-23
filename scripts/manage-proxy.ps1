<#
.SYNOPSIS
    Manage Claude Code Proxy
.PARAMETER Action
    start, stop, restart, status, or switch
#>
param([string]$Action = "status")

$proxyRoot = $PSScriptRoot | Split-Path
$pidFile = Join-Path $proxyRoot "logs\proxy.pid"

function Start-Proxy {
    if (Test-Path $pidFile) {
        $proxyPid = Get-Content $pidFile
        if (Get-Process -Id $proxyPid -ErrorAction SilentlyContinue) {
            Write-Host "Proxy already running (PID: $proxyPid)" -ForegroundColor Yellow
            return
        }
    }
    
    Push-Location $proxyRoot
    $process = Start-Process python -ArgumentList "proxy.py" -WindowStyle Hidden -PassThru
    $process.Id | Out-File $pidFile
    Pop-Location
    
    Start-Sleep -Seconds 2
    Write-Host "Proxy started (PID: $($process.Id))" -ForegroundColor Green
    Write-Host "Dashboard: http://localhost:8082/dashboard" -ForegroundColor Cyan
}

function Stop-Proxy {
    if (!(Test-Path $pidFile)) {
        Write-Host "Proxy not running" -ForegroundColor Yellow
        return
    }
    
    $proxyPid = Get-Content $pidFile
    Stop-Process -Id $proxyPid -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Proxy stopped" -ForegroundColor Green
}

function Get-ProxyStatus {
    if (!(Test-Path $pidFile)) {
        Write-Host "Status: STOPPED" -ForegroundColor Red
        return
    }
    
    $proxyPid = Get-Content $pidFile
    $process = Get-Process -Id $proxyPid -ErrorAction SilentlyContinue
    
    if (!$process) {
        Write-Host "Status: STOPPED (stale PID file)" -ForegroundColor Red
        Remove-Item $pidFile -Force
        return
    }
    
    Write-Host "Status: RUNNING" -ForegroundColor Green
    Write-Host "  PID: $proxyPid"
    Write-Host "  Uptime: $((Get-Date) - $process.StartTime)"
    Write-Host "  Memory: $([math]::Round($process.WorkingSet64 / 1MB, 2)) MB"
    Write-Host ""
    Write-Host "Dashboard: http://localhost:8082/dashboard" -ForegroundColor Cyan
    
    # Test health
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8082/health" -TimeoutSec 2 -UseBasicParsing
        Write-Host "Health: OK" -ForegroundColor Green
    } catch {
        Write-Host "Health: FAILED" -ForegroundColor Red
    }
}

switch ($Action.ToLower()) {
    "start"   { Start-Proxy }
    "stop"    { Stop-Proxy }
    "restart" { Stop-Proxy; Start-Sleep -Seconds 1; Start-Proxy }
    "status"  { Get-ProxyStatus }
    default   { 
        Write-Host "Usage: .\manage-proxy.ps1 [start|stop|restart|status]" -ForegroundColor Yellow
        Get-ProxyStatus
    }
}
