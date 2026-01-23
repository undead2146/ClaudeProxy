<#
.SYNOPSIS
    Manage Claude Code Proxy, Antigravity Server, and GitHub Copilot API
.PARAMETER Action
    start, stop, restart, status
.DESCRIPTION
    This script manages the main proxy server, Antigravity server, and GitHub Copilot API.
    Use 'start' to start all services, 'stop' to stop all, etc.
#>
param([string]$Action = "status")

$proxyRoot = $PSScriptRoot | Split-Path
$pidFile = Join-Path $proxyRoot "logs\proxy.pid"
$antigravityPidFile = Join-Path $proxyRoot "logs\antigravity.pid"
$copilotPidFile = Join-Path $proxyRoot "logs\copilot.pid"

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

function Start-Copilot {
    # Check if already running
    if (Test-Path $copilotPidFile) {
        $cpPid = Get-Content $copilotPidFile
        if (Get-Process -Id $cpPid -ErrorAction SilentlyContinue) {
            Write-Host "[Copilot] Already running (PID: $cpPid)" -ForegroundColor Yellow
            return $cpPid
        }
    }
    
    Write-Host "[Copilot] Starting GitHub Copilot API on port 4141..." -ForegroundColor Cyan
    
    # Create log directory
    $logDir = Join-Path $proxyRoot "logs"
    if (!(Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir | Out-Null
    }
    
    # Start Copilot API
    $cpProcess = Start-Process npx -ArgumentList "copilot-api@latest", "start", "--port", "4141" -WindowStyle Hidden -PassThru
    $cpProcess.Id | Out-File $copilotPidFile
    
    # Wait for Copilot to be ready
    Start-Sleep -Seconds 3
    
    # Verify it's responding
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:4141/usage" -TimeoutSec 3 -UseBasicParsing
        $usage = $response.Content | ConvertFrom-Json
        $remaining = [math]::Floor($usage.quota_snapshots.premium_interactions.remaining)
        $total = $usage.quota_snapshots.premium_interactions.entitlement
        Write-Host "[Copilot] Started successfully (PID: $($cpProcess.Id))" -ForegroundColor Green
        Write-Host "[Copilot] Premium Quota: $remaining / $total remaining" -ForegroundColor Cyan
    } catch {
        Write-Host "[Copilot] Started but not responding yet" -ForegroundColor Yellow
    }
    
    return $cpProcess.Id
}

function Start-Proxy {
    # First start Antigravity and Copilot
    Start-Antigravity
    Start-Copilot
    
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

function Stop-Copilot {
    if (!(Test-Path $copilotPidFile)) {
        Write-Host "[Copilot] Not running" -ForegroundColor Yellow
        return
    }
    
    $cpPid = Get-Content $copilotPidFile
    
    # Stop the process
    Stop-Process -Id $cpPid -Force -ErrorAction SilentlyContinue
    
    # Also kill any node processes on port 4141
    $nodeProcesses = Get-NetTCPConnection -LocalPort 4141 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($nodePid in $nodeProcesses) {
        Stop-Process -Id $nodePid -Force -ErrorAction SilentlyContinue
    }
    
    Remove-Item $copilotPidFile -Force -ErrorAction SilentlyContinue
    Write-Host "[Copilot] Stopped" -ForegroundColor Green
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
    
    # Stop Copilot
    Stop-Copilot
    
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
    
    # Check GitHub Copilot API
    Write-Host "" 
    Write-Host "[GitHub Copilot API]" -ForegroundColor Yellow
    $cpRunning = $false
    if (Test-Path $copilotPidFile) {
        $cpPid = Get-Content $copilotPidFile
        $cpProcess = Get-Process -Id $cpPid -ErrorAction SilentlyContinue
        
        if ($cpProcess) {
            Write-Host "  Status: RUNNING" -ForegroundColor Green
            Write-Host "  PID: $cpPid"
            $cpRunning = $true
        } else {
            Write-Host "  Status: STOPPED (stale PID)" -ForegroundColor Red
            Remove-Item $copilotPidFile -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "  Status: STOPPED" -ForegroundColor Red
    }
    
    # Test Copilot health
    if ($cpRunning) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:4141/usage" -TimeoutSec 2 -UseBasicParsing
            $usage = $response.Content | ConvertFrom-Json
            Write-Host "  Health: OK" -ForegroundColor Green
            
            $premium = $usage.quota_snapshots.premium_interactions
            $remaining = [math]::Floor($premium.remaining)
            $total = $premium.entitlement
            $used = $total - $remaining
            $percent = [math]::Round($premium.percent_remaining, 1)
            
            Write-Host "  Premium Quota: $remaining / $total remaining ($percent%)" -ForegroundColor Cyan
            Write-Host "  Used: $used interactions" -ForegroundColor Gray
            Write-Host "  Reset Date: $($usage.quota_reset_date)" -ForegroundColor Gray
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
