#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs the Claude Proxy as a background daemon (Windows Service/Task).
.DESCRIPTION
    This script configures the Claude Code Proxy to run automatically at system boot
    using Windows Task Scheduler. This allows the proxy to run in the background
    without any user being logged in, effectively acting as a system daemon.
#>

$TaskName = "ClaudeProxyDaemon"
$ProxyRoot = Split-Path -Parent $PSScriptRoot
$ServerDir = Join-Path $ProxyRoot "server"
$ProxyScript = Join-Path $ServerDir "proxy.py"
$ManageScript = Join-Path $PSScriptRoot "manage-proxy.ps1"
$LogDir = Join-Path $ProxyRoot "logs"

# Verify Admin
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Please run this script as Administrator." -ForegroundColor Red
    exit
}

Write-Host "--- Claude Proxy Daemon Installer ---" -ForegroundColor Cyan

# Create logs directory
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

# Define the action: Run manage-proxy.ps1 start
$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$ManageScript`" start" `
    -WorkingDirectory $ProxyRoot

# Define the trigger: At system startup
$Trigger = New-ScheduledTaskTrigger -AtStartup

# Define the settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Register the task
$TaskParams = @{
    TaskName = $TaskName
    Action = $Action
    Trigger = $Trigger
    Settings = $Settings
    User = "SYSTEM" # Runs as SYSTEM so it's active before login
    RunLevel = "Highest"
    Description = "Claude Code Proxy Background Daemon"
    Force = $true
}

Register-ScheduledTask @TaskParams | Out-Null

Write-Host "Success! Claude Proxy has been installed as a daemon." -ForegroundColor Green
Write-Host "It will now start automatically on every boot." -ForegroundColor Green
Write-Host "To manage it manually, use: .\manage-proxy.ps1" -ForegroundColor Gray
Write-Host "To uninstall, run: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Red
