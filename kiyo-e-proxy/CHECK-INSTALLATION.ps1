# Check Installation Status
# This script verifies all prerequisites are installed

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  @kiyo-e/claude-code-proxy Installation Check" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Check Node.js
Write-Host "[1/7] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    if ($nodeVersion -match "v\d+\.\d+\.\d+") {
        Write-Host "   Installed: $nodeVersion" -ForegroundColor Green
        
        # Check version is 16 or higher
        $versionNumber = [int]($nodeVersion -replace 'v(\d+)\..*', '$1')
        if ($versionNumber -lt 16) {
            Write-Host "   Warning: Node.js v16+ recommended (you have v$versionNumber)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   Not installed or not in PATH" -ForegroundColor Red
        Write-Host "   Install from: https://nodejs.org/" -ForegroundColor Yellow
        $allGood = $false
    }
} catch {
    Write-Host "   Not installed" -ForegroundColor Red
    Write-Host "   Install from: https://nodejs.org/" -ForegroundColor Yellow
    $allGood = $false
}

# Check npm
Write-Host "[2/7] Checking npm..." -ForegroundColor Yellow
try {
    $npmVersion = npm --version 2>&1
    if ($npmVersion -match "\d+\.\d+\.\d+") {
        Write-Host "   Installed: v$npmVersion" -ForegroundColor Green
    } else {
        Write-Host "   Not installed or not in PATH" -ForegroundColor Red
        $allGood = $false
    }
} catch {
    Write-Host "   Not installed" -ForegroundColor Red
    Write-Host "   (Comes with Node.js)" -ForegroundColor Yellow
    $allGood = $false
}

# Check @kiyo-e/claude-code-proxy
Write-Host "[3/7] Checking @kiyo-e/claude-code-proxy..." -ForegroundColor Yellow
try {
    $proxyCheck = npm list -g @kiyo-e/claude-code-proxy 2>&1
    if ($proxyCheck -like "*@kiyo-e/claude-code-proxy*") {
        Write-Host "   Installed globally" -ForegroundColor Green
    } else {
        Write-Host "   Not installed globally" -ForegroundColor Yellow
        Write-Host "   (Can use npx without installation)" -ForegroundColor Gray
    }
} catch {
    Write-Host "   Not installed globally" -ForegroundColor Yellow
    Write-Host "   (Can use npx without installation)" -ForegroundColor Gray
}

# Check Python (optional)
Write-Host "[4/7] Checking Python (optional)..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python \d+\.\d+\.\d+") {
        Write-Host "   Installed: $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "   Not installed" -ForegroundColor Gray
        Write-Host "   (Only needed for Python proxy alternative)" -ForegroundColor Gray
    }
} catch {
    Write-Host "   Not installed" -ForegroundColor Gray
    Write-Host "   (Only needed for Python proxy alternative)" -ForegroundColor Gray
}

# Check .env file
Write-Host "[5/7] Checking .env configuration..." -ForegroundColor Yellow
$envPath = "C:\tools\claude-code-proxy\kiyo-e-proxy\.env"
if (Test-Path $envPath) {
    Write-Host "   Found: $envPath" -ForegroundColor Green
    
    # Check if it has the required keys
    $envContent = Get-Content $envPath -Raw
    if ($envContent -match "OPENAI_API_BASE" -and $envContent -match "OPENAI_API_KEY") {
        Write-Host "   Configuration looks good" -ForegroundColor Green
    } else {
        Write-Host "   Warning: Missing required configuration" -ForegroundColor Yellow
        $allGood = $false
    }
} else {
    Write-Host "   Not found: $envPath" -ForegroundColor Red
    $allGood = $false
}

# Check Claude settings
Write-Host "[6/7] Checking Claude Code settings..." -ForegroundColor Yellow
$settingsPath = "$env:USERPROFILE\.claude\settings.json"
if (Test-Path $settingsPath) {
    Write-Host "   Found: $settingsPath" -ForegroundColor Green
    
    # Check if it has the required configuration
    $settingsContent = Get-Content $settingsPath -Raw
    if ($settingsContent -match "ANTHROPIC_BASE_URL") {
        Write-Host "   Configuration looks good" -ForegroundColor Green
    } else {
        Write-Host "   Warning: Missing ANTHROPIC_BASE_URL" -ForegroundColor Yellow
    }
} else {
    Write-Host "   Not found" -ForegroundColor Yellow
    Write-Host "   Run: .\CONFIGURE-CLAUDE.ps1" -ForegroundColor Gray
}

# Check port 8080
Write-Host "[7/7] Checking port 8080..." -ForegroundColor Yellow
$portCheck = netstat -an | findstr "8080"
if ($portCheck) {
    Write-Host "   Port 8080 is in use" -ForegroundColor Yellow
    Write-Host "   (Stop existing proxy or change PORT in .env)" -ForegroundColor Gray
} else {
    Write-Host "   Port 8080 is available" -ForegroundColor Green
}

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan

# Summary
if ($allGood) {
    Write-Host "  All required components are installed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Configure Claude Code: .\CONFIGURE-CLAUDE.ps1" -ForegroundColor White
    Write-Host "  2. Start the proxy: .\START-PROXY.ps1" -ForegroundColor White
    Write-Host "  3. Test connection: .\TEST-PROXY.ps1" -ForegroundColor White
} else {
    Write-Host "  Some components are missing!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install the missing components and try again." -ForegroundColor Yellow
    Write-Host "See INSTALLATION-CHECK.md for detailed instructions." -ForegroundColor Yellow
}

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""
