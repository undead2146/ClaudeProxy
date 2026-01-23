<#
.SYNOPSIS
    Switch Claude Code Proxy providers dynamically
.DESCRIPTION
    Easily switch between providers (antigravity, glm, anthropic, copilot) without restarting
.PARAMETER Tier
    The model tier to configure: sonnet, haiku, opus, or all
.PARAMETER Provider
    The provider to use: antigravity, glm, anthropic, copilot
.EXAMPLE
    .\switch-provider.ps1 -Tier sonnet -Provider copilot
.EXAMPLE
    .\switch-provider.ps1 -Tier all -Provider antigravity
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('sonnet', 'haiku', 'opus', 'all')]
    [string]$Tier,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet('antigravity', 'glm', 'anthropic', 'copilot')]
    [string]$Provider
)

$ErrorActionPreference = 'Stop'

Write-Host "Switching $Tier provider to $Provider..." -ForegroundColor Cyan

try {
    if ($Tier -eq 'all') {
        $body = @{
            sonnet_provider = $Provider
            haiku_provider = $Provider
            opus_provider = $Provider
        } | ConvertTo-Json
    } else {
        $key = "${Tier}_provider"
        $body = @{
            $key = $Provider
        } | ConvertTo-Json
    }
    
    $response = Invoke-RestMethod -Method POST -Uri "http://localhost:8082/config" -ContentType "application/json" -Body $body
    
    Write-Host "✓ Success!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Current Configuration:" -ForegroundColor Yellow
    Write-Host "  Sonnet: $($response.config.sonnet_provider)" -ForegroundColor White
    Write-Host "  Haiku:  $($response.config.haiku_provider)" -ForegroundColor White
    Write-Host "  Opus:   $($response.config.opus_provider)" -ForegroundColor White
    Write-Host ""
    Write-Host "Changes are effective immediately (no restart needed)!" -ForegroundColor Green
    
} catch {
    Write-Host "✗ Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Is the proxy running? Check with: .\scripts\status-proxy.ps1" -ForegroundColor Yellow
    exit 1
}
