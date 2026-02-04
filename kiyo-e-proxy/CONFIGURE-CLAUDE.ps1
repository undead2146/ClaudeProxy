# Configure Claude Code to use the @kiyo-e/claude-code-proxy
# This script creates the settings.json file for Claude Code

Write-Host "Configuring Claude Code to use local proxy..." -ForegroundColor Cyan
Write-Host ""

# Define the Claude settings directory and file
$claudeDir = "$env:USERPROFILE\.claude"
$settingsFile = "$claudeDir\settings.json"

# Create directory if it doesn't exist
if (-not (Test-Path $claudeDir)) {
    Write-Host "Creating Claude settings directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null
    Write-Host " Created: $claudeDir" -ForegroundColor Green
} else {
    Write-Host " Claude settings directory exists" -ForegroundColor Green
}

# Check if settings file already exists
if (Test-Path $settingsFile) {
    Write-Host ""
    Write-Host " Settings file already exists!" -ForegroundColor Yellow
    Write-Host "  Location: $settingsFile" -ForegroundColor White
    Write-Host ""
    
    $backup = "$settingsFile.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Write-Host "Creating backup: $backup" -ForegroundColor Yellow
    Copy-Item $settingsFile $backup
    Write-Host " Backup created" -ForegroundColor Green
}

# Create the settings.json content
$settingsContent = @"
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8080",
    "ANTHROPIC_API_KEY": "dummy-key-not-used",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "API_TIMEOUT_MS": "3000000"
  }
}
"@

# Write the settings file
Write-Host ""
Write-Host "Writing settings file..." -ForegroundColor Yellow
$settingsContent | Out-File -FilePath $settingsFile -Encoding UTF8 -Force

Write-Host " Settings file created" -ForegroundColor Green
Write-Host ""

# Display the configuration
Write-Host "Claude Code Configuration:" -ForegroundColor Cyan
Write-Host "  ANTHROPIC_BASE_URL: http://localhost:8080" -ForegroundColor White
Write-Host "  ANTHROPIC_API_KEY: dummy-key-not-used" -ForegroundColor White
Write-Host "  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: 1" -ForegroundColor White
Write-Host "  API_TIMEOUT_MS: 3000000" -ForegroundColor White
Write-Host ""

Write-Host " Configuration complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start the proxy: .\START-PROXY.ps1" -ForegroundColor White
Write-Host "  2. Verify proxy is running: curl http://localhost:8080/health" -ForegroundColor White
Write-Host "  3. Start Claude Code (it will now use the proxy)" -ForegroundColor White
Write-Host ""
Write-Host "Note: The ANTHROPIC_API_KEY value doesn't matter - the proxy uses" -ForegroundColor Yellow
Write-Host "      the EnowDev API key from the .env file." -ForegroundColor Yellow
Write-Host ""
