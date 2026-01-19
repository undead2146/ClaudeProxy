#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Starts the Claude Code Proxy server in the background.

.DESCRIPTION
    This script sets up the required environment variables and starts the proxy server
    as a background process. Logs are written to the logs directory.

.EXAMPLE
    .\start-proxy.ps1
    Starts the proxy server with default settings.
#>

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Define paths
$ProxyRoot = Split-Path -Parent $PSScriptRoot
$ProxyScript = Join-Path $ProxyRoot "proxy.py"
$LogDir = Join-Path $ProxyRoot "logs"
$LogFile = Join-Path $LogDir "proxy.log"
$PidFile = Join-Path $LogDir "proxy.pid"
$EnvFile = Join-Path $ProxyRoot ".env"

# Create logs directory if it doesn't exist
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

# Check if proxy is already running
if (Test-Path $PidFile) {
    $proxyPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($proxyPid) {
        $process = Get-Process -Id $proxyPid -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -eq "python") {
            if ($Force) {
                Write-Host "Proxy already running (PID: $proxyPid). Stopping existing instance..." -ForegroundColor Yellow
                & "$PSScriptRoot\stop-proxy.ps1"
                Start-Sleep -Seconds 2
            } else {
                Write-Host "Proxy is already running (PID: $proxyPid)" -ForegroundColor Yellow
                Write-Host "Use -Force to restart the proxy" -ForegroundColor Yellow
                exit 1
            }
        } else {
            # Stale PID file
            Remove-Item $PidFile -Force
        }
    }
}

# Load environment variables from .env file
if (Test-Path $EnvFile) {
    Write-Host "Loading environment variables from .env file..." -ForegroundColor Cyan
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)\s*=\s*(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
            Write-Host "  Set $name" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "WARNING: .env file not found at $EnvFile" -ForegroundColor Yellow
    Write-Host "Environment variables must be set manually or create .env file" -ForegroundColor Yellow
}

# Verify Python is available
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "Using $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found. Please install Python 3.11+ and add to PATH" -ForegroundColor Red
    exit 1
}

# Verify proxy script exists
if (-not (Test-Path $ProxyScript)) {
    Write-Host "ERROR: Proxy script not found at $ProxyScript" -ForegroundColor Red
    exit 1
}

# Start the proxy server in the background
Write-Host "Starting Claude Code Proxy..." -ForegroundColor Cyan
Write-Host "Proxy Root: $ProxyRoot" -ForegroundColor Gray
Write-Host "Log File: $LogFile" -ForegroundColor Gray

# Set log file environment variable for the process
[Environment]::SetEnvironmentVariable("CLAUDE_PROXY_LOG_FILE", $LogFile, "Process")

# Start Python process in background
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = "python"
$processInfo.Arguments = "-u `"$ProxyScript`""
$processInfo.WorkingDirectory = $ProxyRoot
$processInfo.UseShellExecute = $false
$processInfo.RedirectStandardOutput = $false
$processInfo.RedirectStandardError = $false
$processInfo.CreateNoWindow = $true

# Copy current environment variables
foreach ($key in [Environment]::GetEnvironmentVariables("Process").Keys) {
    $value = [Environment]::GetEnvironmentVariable($key, "Process")
    $processInfo.EnvironmentVariables[$key] = $value
}

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $processInfo

# Start the process
$process.Start() | Out-Null

# Save PID
$process.Id | Out-File -FilePath $PidFile -Encoding ascii

# Wait a moment to check if process started successfully
Start-Sleep -Seconds 2

if ($process.HasExited) {
    Write-Host "ERROR: Proxy process exited immediately. Check logs:" -ForegroundColor Red
    Write-Host $LogFile -ForegroundColor Yellow
    Get-Content $LogFile -Tail 20
    exit 1
}

Write-Host "Proxy started successfully!" -ForegroundColor Green
Write-Host "PID: $($process.Id)" -ForegroundColor Green
Write-Host "Log: $LogFile" -ForegroundColor Gray
Write-Host ""
Write-Host "Use the following commands to manage the proxy:" -ForegroundColor Cyan
Write-Host "  .\scripts\status-proxy.ps1  - Check proxy status" -ForegroundColor Gray
Write-Host "  .\scripts\test-proxy.ps1    - Test proxy health" -ForegroundColor Gray
Write-Host "  .\scripts\restart-proxy.ps1 - Restart proxy" -ForegroundColor Gray
Write-Host "  .\scripts\stop-proxy.ps1    - Stop proxy" -ForegroundColor Gray
Write-Host ""
Write-Host "Tail logs with: Get-Content '$LogFile' -Tail 50 -Wait" -ForegroundColor Gray
