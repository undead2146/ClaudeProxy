# Test the @kiyo-e/claude-code-proxy connection to EnowDev
# This script verifies the proxy is working correctly

Write-Host "Testing @kiyo-e/claude-code-proxy connection..." -ForegroundColor Cyan
Write-Host ""

# Test 1: Check if proxy is running
Write-Host "[Test 1] Checking if proxy is running on port 8080..." -ForegroundColor Yellow

try {
    $healthCheck = Invoke-WebRequest -Uri "http://localhost:8080/health" -Method GET -ErrorAction Stop
    Write-Host " Proxy is running" -ForegroundColor Green
    Write-Host "  Status: $($healthCheck.StatusCode)" -ForegroundColor White
} catch {
    Write-Host " Proxy is not running!" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Start the proxy first:" -ForegroundColor Yellow
    Write-Host "  .\START-PROXY.ps1" -ForegroundColor White
    exit 1
}

Write-Host ""

# Test 2: Send a test request
Write-Host "[Test 2] Sending test request to proxy..." -ForegroundColor Yellow

$testRequest = @{
    model = "claude-3-7-sonnet"
    max_tokens = 100
    messages = @(
        @{
            role = "user"
            content = "Say 'Hello from EnowDev!' and nothing else."
        }
    )
} | ConvertTo-Json -Depth 10

$headers = @{
    "Content-Type" = "application/json"
    "x-api-key" = "test"
    "anthropic-version" = "2023-06-01"
}

try {
    Write-Host "  Sending request to: http://localhost:8080/v1/messages" -ForegroundColor White
    Write-Host "  Model: claude-3-7-sonnet (should be translated to claude-3.7-sonnet)" -ForegroundColor White
    Write-Host ""
    
    $response = Invoke-WebRequest -Uri "http://localhost:8080/v1/messages" `
        -Method POST `
        -Headers $headers `
        -Body $testRequest `
        -ContentType "application/json" `
        -ErrorAction Stop
    
    Write-Host " Request successful!" -ForegroundColor Green
    Write-Host "  Status: $($response.StatusCode)" -ForegroundColor White
    Write-Host ""
    
    # Parse and display response
    $responseData = $response.Content | ConvertFrom-Json
    Write-Host "Response:" -ForegroundColor Cyan
    Write-Host "  Model: $($responseData.model)" -ForegroundColor White
    Write-Host "  Content: $($responseData.content[0].text)" -ForegroundColor White
    Write-Host ""
    
    Write-Host " All tests passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The proxy is working correctly with EnowDev!" -ForegroundColor Green
    
} catch {
    Write-Host " Request failed!" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    
    # Check for common errors
    if ($_.Exception.Message -like "*404*") {
        Write-Host " 404 Error - This likely means the proxy is appending /v1 to the URL" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "EnowDev does NOT use /v1 path:" -ForegroundColor Yellow
        Write-Host "   Correct: https://api.enowdev.id/messages" -ForegroundColor Green
        Write-Host "   Wrong:   https://api.enowdev.id/v1/messages" -ForegroundColor Red
        Write-Host ""
        Write-Host "Solutions:" -ForegroundColor Cyan
        Write-Host "  1. Check if the proxy supports OPENAI_API_PATH configuration" -ForegroundColor White
        Write-Host "  2. Use the Python proxy instead (already supports SKIP_V1)" -ForegroundColor White
        Write-Host "  3. Set up a reverse proxy (nginx/Caddy) to rewrite URLs" -ForegroundColor White
        Write-Host ""
    } elseif ($_.Exception.Message -like "*401*" -or $_.Exception.Message -like "*403*") {
        Write-Host " Authentication Error" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Check your API key in .env file:" -ForegroundColor Yellow
        Write-Host "  OPENAI_API_KEY=enx_..." -ForegroundColor White
        Write-Host ""
    } elseif ($_.Exception.Message -like "*model*") {
        Write-Host " Model Name Error" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "The model name mapping may not be working." -ForegroundColor Yellow
        Write-Host "Check .env file has:" -ForegroundColor Yellow
        Write-Host "  CLAUDE_37_SONNET=claude-3.7-sonnet" -ForegroundColor White
        Write-Host ""
    }
    
    Write-Host "Check the proxy logs for more details." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Configure Claude Code: .\CONFIGURE-CLAUDE.ps1" -ForegroundColor White
Write-Host "  2. Start using Claude Code normally" -ForegroundColor White
Write-Host ""
