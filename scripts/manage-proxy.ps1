<#
.SYNOPSIS
    Manage Claude Code Proxy and Antigravity Server
.PARAMETER Action
    start, stop, restart, status
.DESCRIPTION
    This script manages both the main proxy server and the Antigravity server.
    Use 'start' to start both services, 'stop' to stop both, etc.
#>
param([string]$Action = "status")

$proxyRoot = $PSScriptRoot | Split-Path
$pidFile = Join-Path $proxyRoot "logs\proxy.pid"
$antigravityPidFile = Join-Path $proxyRoot "logs\antigravity.pid"

function Start-Antigravity {
    # Check if already running
    if (Test-Path $antigravityPidFile) {
        $agPid = Get-Content $antigravityPidFile
        if (Get-Process -Id $agPid -ErrorAction SilentlyContinue) {
            Write-Host "[Antigravity] Already running (PID: $agPid)" -ForegroundColor Yellow
            return $agPid
        }
    }
    
    Write-Host "[Antigravity] Starting server on port 8081..." -ForegroundColor Cyan
    Write-Host "[Antigravity] If you see errors, run: antigravity-claude-proxy accounts" -ForegroundColor Yellow
    
    # Create log directory
    $logDir = Join-Path $proxyRoot "logs"
    if (!(Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir | Out-Null
    }
    
    # Start Antigravity with redirected output to log file
    $agLogFile = Join-Path $logDir "antigravity.log"
    $agProcess = Start-Process powershell -ArgumentList "-Command", "`$env:PORT=8081; antigravity-claude-proxy start 2>&1 | Tee-Object -FilePath '$agLogFile'" -WindowStyle Minimized -PassThru
    $agProcess.Id | Out-File $antigravityPidFile
    
    # Wait for Antigravity to be ready
    Start-Sleep -Seconds 5
    
    # Verify it's responding
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8081/health" -TimeoutSec 3 -UseBasicParsing
        Write-Host "[Antigravity] Started successfully (PID: $($agProcess.Id))" -ForegroundColor Green
        Write-Host "[Antigravity] Dashboard: http://localhost:8081" -ForegroundColor Cyan
        Write-Host "[Antigravity] Logs: $agLogFile" -ForegroundColor Gray
    } catch {
        Write-Host "[Antigravity] Started but not responding yet. Check logs:" -ForegroundColor Yellow
        Write-Host "  $agLogFile" -ForegroundColor Gray
    }
    
    return $agProcess.Id
}

function Start-Proxy {
    # First start Antigravity
    Start-Antigravity
    
    # Then start the main proxy
    if (Test-Path $pidFile) {
        $proxyPid = Get-Content $pidFile
        if (Get-Process -Id $proxyPid -ErrorAction SilentlyContinue) {
            Write-Host "[Proxy] Already running (PID: $proxyPid)" -ForegroundColor Yellow
            return
        }
    }
    
    Write-Host "[Proxy] Starting server..." -ForegroundColor Cyan
    Push-Location $proxyRoot
    $process = Start-Process python -ArgumentList "proxy.py" -WindowStyle Hidden -PassThru
    $process.Id | Out-File $pidFile
    Pop-Location
    
    Start-Sleep -Seconds 2
    Write-Host "[Proxy] Started successfully (PID: $($process.Id))" -ForegroundColor Green
    Write-Host "[Proxy] Dashboard: http://localhost:8082/dashboard" -ForegroundColor Cyan
    Write-Host "" 
    Write-Host "======================================" -ForegroundColor Green
    Write-Host "All services started successfully!" -ForegroundColor Green
    Write-Host "======================================" -ForegroundColor Green
}

function Stop-Antigravity {
    if (!(Test-Path $antigravityPidFile)) {
        Write-Host "[Antigravity] Not running" -ForegroundColor Yellow
        return
    }
    
    $agPid = Get-Content $antigravityPidFile
    
    # Stop the PowerShell window hosting Antigravity
    Stop-Process -Id $agPid -Force -ErrorAction SilentlyContinue
    
    # Also kill any node processes on port 8081
    $nodeProcesses = Get-NetTCPConnection -LocalPort 8081 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($nodePid in $nodeProcesses) {
        Stop-Process -Id $nodePid -Force -ErrorAction SilentlyContinue
    }
    
    Remove-Item $antigravityPidFile -Force -ErrorAction SilentlyContinue
    Write-Host "[Antigravity] Stopped" -ForegroundColor Green
}

function Stop-Proxy {
    # Stop main proxy
    if (!(Test-Path $pidFile)) {
        Write-Host "[Proxy] Not running" -ForegroundColor Yellow
    } else {
        $proxyPid = Get-Content $pidFile
        Stop-Process -Id $proxyPid -Force -ErrorAction SilentlyContinue
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        Write-Host "[Proxy] Stopped" -ForegroundColor Green
    }
    
    # Stop Antigravity
    Stop-Antigravity
    
    Write-Host "" 
    Write-Host "All services stopped" -ForegroundColor Green
}

function Get-ProxyStatus {
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "Service Status" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    
    # Check Antigravity
    Write-Host "" 
    Write-Host "[Antigravity Server]" -ForegroundColor Yellow
    $agRunning = $false
    if (Test-Path $antigravityPidFile) {
        $agPid = Get-Content $antigravityPidFile
        $agProcess = Get-Process -Id $agPid -ErrorAction SilentlyContinue
        
        if ($agProcess) {
            Write-Host "  Status: RUNNING" -ForegroundColor Green
            Write-Host "  PID: $agPid"
            $agRunning = $true
        } else {
            Write-Host "  Status: STOPPED (stale PID)" -ForegroundColor Red
            Remove-Item $antigravityPidFile -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "  Status: STOPPED" -ForegroundColor Red
    }
    
    # Test Antigravity health
    if ($agRunning) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8081/health" -TimeoutSec 2 -UseBasicParsing
            Write-Host "  Health: OK" -ForegroundColor Green
            Write-Host "  Dashboard: http://localhost:8081" -ForegroundColor Cyan
        } catch {
            Write-Host "  Health: FAILED" -ForegroundColor Red
        }
    }
    
    # Check Main Proxy
    Write-Host "" 
    Write-Host "[Main Proxy Server]" -ForegroundColor Yellow
    if (!(Test-Path $pidFile)) {
        Write-Host "  Status: STOPPED" -ForegroundColor Red
        return
    }
    
    $proxyPid = Get-Content $pidFile
    $process = Get-Process -Id $proxyPid -ErrorAction SilentlyContinue
    
    if (!$process) {
        Write-Host "  Status: STOPPED (stale PID file)" -ForegroundColor Red
        Remove-Item $pidFile -Force
        return
    }
    
    Write-Host "  Status: RUNNING" -ForegroundColor Green
    Write-Host "  PID: $proxyPid"
    Write-Host "  Uptime: $((Get-Date) - $process.StartTime)"
    Write-Host "  Memory: $([math]::Round($process.WorkingSet64 / 1MB, 2)) MB"
    
    # Test proxy health
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8082/health" -TimeoutSec 2 -UseBasicParsing
        Write-Host "  Health: OK" -ForegroundColor Green
        Write-Host "  Dashboard: http://localhost:8082/dashboard" -ForegroundColor Cyan
    } catch {
        Write-Host "  Health: FAILED" -ForegroundColor Red
    }
    
    Write-Host "" 
    Write-Host "======================================" -ForegroundColor Cyan
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
