#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Configures Windows Firewall to allow Claude Code Proxy network access.

.DESCRIPTION
    Adds a firewall rule to allow incoming connections on port 8082 from local subnet.

.EXAMPLE
    .\setup-firewall.ps1
    Adds or updates the firewall rule.
#>

$ErrorActionPreference = "Stop"

Write-Host "Configuring Windows Firewall for Claude Code Proxy..." -ForegroundColor Cyan
Write-Host ""

# Check if rule already exists
$existingRule = Get-NetFirewallRule -DisplayName "Claude Code Proxy" -ErrorAction SilentlyContinue

if ($existingRule) {
    Write-Host "Existing firewall rule found. Removing..." -ForegroundColor Yellow
    Remove-NetFirewallRule -DisplayName "Claude Code Proxy"
}

# Add new firewall rule
Write-Host "Adding firewall rule..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "Claude Code Proxy" `
    -Description "Allow incoming connections to Claude Code Proxy on port 8082" `
    -Direction Inbound `
    -LocalPort 8082 `
    -Protocol TCP `
    -Action Allow `
    -Profile Private,Domain `
    -RemoteAddress LocalSubnet `
    -Enabled True | Out-Null

Write-Host "(OK) Firewall rule added successfully!" -ForegroundColor Green
Write-Host ""

# Verify the rule
$rule = Get-NetFirewallRule -DisplayName "Claude Code Proxy"
Write-Host "Rule Details:" -ForegroundColor Cyan
Write-Host "  Name:        $($rule.DisplayName)" -ForegroundColor Gray
Write-Host "  Enabled:     $($rule.Enabled)" -ForegroundColor Gray
Write-Host "  Direction:   $($rule.Direction)" -ForegroundColor Gray
Write-Host "  Action:      $($rule.Action)" -ForegroundColor Gray
Write-Host "  Profile:     $($rule.Profile)" -ForegroundColor Gray

# Get port filter
$portFilter = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $rule
Write-Host "  Protocol:    $($portFilter.Protocol)" -ForegroundColor Gray
Write-Host "  Local Port:  $($portFilter.LocalPort)" -ForegroundColor Gray

# Get address filter
$addressFilter = Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $rule
Write-Host "  Remote Addr: $($addressFilter.RemoteAddress)" -ForegroundColor Gray

Write-Host ""
Write-Host "Firewall is now configured. Test with:" -ForegroundColor Yellow
Write-Host "  curl http://192.168.1.16:8082/health" -ForegroundColor Gray
Write-Host ""
