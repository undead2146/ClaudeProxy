# Start @kiyo-e/claude-code-proxy with EnowDev configuration
# This script starts the Node.js proxy with proper environment variables

Write-Host "Starting @kiyo-e/claude-code-proxy for EnowDev..." -ForegroundColor Cyan
Write-Host ""

# Check if Node.js is installed
try {
    $nodeVersion = node --version
    Write-Host " Node.js version: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host " Node.js is not installed!" -ForegroundColor Red
    Write-Host "  Download from: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# Check if npm is installed
try {
    $npmVersion = npm --version
    Write-Host " npm version: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host " npm is not installed!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Change to the kiyo-e-proxy directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Check if .env file exists
if (Test-Path ".env") {
    Write-Host " Found .env configuration file" -ForegroundColor Green
} else {
    Write-Host " .env file not found!" -ForegroundColor Red
    Write-Host "  Expected location: $scriptDir\.env" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  API Base: https://api.enowdev.id" -ForegroundColor White
Write-Host "  Proxy Port: 8080" -ForegroundColor White
Write-Host "  Debug Mode: Enabled" -ForegroundColor White
Write-Host ""

# Enable debug mode
$env:DEBUG = "*"

Write-Host "Starting proxy server..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""
Write-Host "Watch for these in the logs:" -ForegroundColor Cyan
Write-Host "  1. Incoming Anthropic API format requests" -ForegroundColor White
Write-Host "  2. Model name translation (e.g., claude-3-7-sonnet  claude-3.7-sonnet)" -ForegroundColor White
Write-Host "  3. Outgoing OpenAI API format requests" -ForegroundColor White
Write-Host "  4. URL being called (should be https://api.enowdev.id/...)" -ForegroundColor White
Write-Host "  5. Check if /v1 is being appended (this causes 404 errors)" -ForegroundColor Yellow
Write-Host ""

# Try to run the proxy
try {
    # First try npx (works without installation)
    npx @kiyo-e/claude-code-proxy
} catch {
    Write-Host ""
    Write-Host "Failed to start proxy with npx" -ForegroundColor Red
    Write-Host ""
    Write-Host "Trying to install globally..." -ForegroundColor Yellow
    npm install -g @kiyo-e/claude-code-proxy
    
    Write-Host ""
    Write-Host "Starting proxy..." -ForegroundColor Cyan
    claude-code-proxy
}
