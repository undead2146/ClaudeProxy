#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs the Claude Code Proxy as an auto-start task.

.DESCRIPTION
    This script creates a Windows Task Scheduler task that automatically starts
    the proxy server when the system boots, regardless of user login.

    The task will:
    - Start at system startup (not user logon)
    - Run whether user is logged on or not
    - Run with highest privileges
    - Auto-restart on failure
    - Load environment variables from .env file

.PARAMETER Uninstall
    Remove the auto-start task instead of installing it.

.EXAMPLE
    .\install-autostart.ps1
    Installs the auto-start task.

.EXAMPLE
    .\install-autostart.ps1 -Uninstall
    Removes the auto-start task.
#>

param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

# Task configuration
$TaskName = "Claude Code Proxy Auto-Start"
$TaskDescription = "Automatically starts the Claude Code Proxy server at system startup"

# Define paths
$ProxyRoot = Split-Path -Parent $PSScriptRoot
$ProxyScript = Join-Path $ProxyRoot "proxy.py"
$LogDir = Join-Path $ProxyRoot "logs"
$LogFile = Join-Path $LogDir "proxy.log"
$EnvFile = Join-Path $ProxyRoot ".env"
$StartScript = Join-Path $PSScriptRoot "start-proxy.ps1"

# Verify admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    exit 1
}

# Handle uninstall
if ($Uninstall) {
    Write-Host "Uninstalling auto-start task..." -ForegroundColor Cyan

    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Auto-start task removed successfully" -ForegroundColor Green
    } else {
        Write-Host "Auto-start task not found" -ForegroundColor Yellow
    }
    exit 0
}

# Verify required files exist
if (-not (Test-Path $ProxyScript)) {
    Write-Host "ERROR: Proxy script not found at $ProxyScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $EnvFile)) {
    Write-Host "WARNING: .env file not found at $EnvFile" -ForegroundColor Yellow
    Write-Host "Create .env file with required environment variables before starting" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}

# Create logs directory if it doesn't exist
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

Write-Host "Installing Claude Code Proxy auto-start task..." -ForegroundColor Cyan
Write-Host ""

# Get current user for the task
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Task Name:   $TaskName" -ForegroundColor Gray
Write-Host "  User:        $currentUser" -ForegroundColor Gray
Write-Host "  Proxy:       $ProxyScript" -ForegroundColor Gray
Write-Host "  Logs:        $LogFile" -ForegroundColor Gray
Write-Host ""

# Build PowerShell command to run
# This command will:
# 1. Load environment variables from .env
# 2. Start Antigravity server
# 3. Start Python proxy
# 4. Redirect output to log file
$command = @"
# Load environment variables from .env file
if (Test-Path '$EnvFile') {
    Get-Content '$EnvFile' | ForEach-Object {
        if (`$_ -match '^\s*([^#][^=]*)\s*=\s*(.*)$') {
            `$name = `$matches[1].Trim()
            `$value = `$matches[2].Trim().Trim('""').Trim("'")
            [Environment]::SetEnvironmentVariable(`$name, `$value, 'Process')
        }
    }
}

# Start Antigravity server first
Write-Host '[Startup] Starting Antigravity server on port 8081...'
`$env:PORT = '8081'
Start-Process powershell -ArgumentList '-NoExit', '-Command', '`$env:PORT=8081; antigravity-claude-proxy start' -WindowStyle Minimized

# Wait for Antigravity to start
Start-Sleep -Seconds 5

# Start main proxy and redirect output to log
Write-Host '[Startup] Starting main proxy server...'
[Environment]::SetEnvironmentVariable('CLAUDE_PROXY_LOG_FILE', '$LogFile', 'Process')
python -u '$ProxyScript'
"@

# Create the scheduled task action
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"$command`""

# Create trigger: At system startup
$trigger = New-ScheduledTaskTrigger -AtStartup

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Create principal to run whether user is logged on or not
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType S4U -RunLevel Highest

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Register the task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null

    Write-Host "(OK) Auto-start task installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Details:" -ForegroundColor Cyan
    Write-Host "  - Starts at system startup" -ForegroundColor Gray
    Write-Host "  - Runs whether you're logged in or not" -ForegroundColor Gray
    Write-Host "  - Auto-restarts on failure (up to 3 times)" -ForegroundColor Gray
    Write-Host "  - Logs to: $LogFile" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Management Commands:" -ForegroundColor Cyan
    Write-Host "  Start Task:     Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "  Stop Task:      Stop-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "  View Status:    Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "  Uninstall:      .\scripts\install-autostart.ps1 -Uninstall" -ForegroundColor Gray
    Write-Host ""

    # Ask if user wants to start the task now
    $startNow = Read-Host "Start the proxy now? (Y/n)"
    if ($startNow -ne "n" -and $startNow -ne "N") {
        Write-Host "Starting proxy..." -ForegroundColor Cyan
        Start-ScheduledTask -TaskName $TaskName

        # Wait a moment and check status
        Start-Sleep -Seconds 3

        $task = Get-ScheduledTask -TaskName $TaskName
        Write-Host "Task State: $($task.State)" -ForegroundColor Gray

        if ($task.State -eq "Running") {
            Write-Host "(OK) Proxy started successfully!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Test the proxy with: .\scripts\test-proxy.ps1" -ForegroundColor Yellow
        } else {
            Write-Host "[WARNING] Task may not have started. Check logs:" -ForegroundColor Yellow
            Write-Host "  $LogFile" -ForegroundColor Gray
        }
    }

} catch {
    Write-Host "ERROR: Failed to create scheduled task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
