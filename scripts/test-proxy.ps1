<#
.SYNOPSIS
    Tests the Claude Code Proxy server health and configuration.

.DESCRIPTION
    This script performs comprehensive health checks on the proxy server including:
    - Connectivity test (localhost and network)
    - Health endpoint verification
    - Provider configuration validation
    - OAuth token status

.EXAMPLE
    .\test-proxy.ps1
    Runs all health checks.

.EXAMPLE
    .\test-proxy.ps1 -NetworkIP 192.168.1.16
    Tests network accessibility from specified IP.
#>

param(
    [string]$NetworkIP = "",
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

# ANSI color codes
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Cyan = "`e[36m"
$Reset = "`e[0m"

$testsPassed = 0
$testsFailed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [scriptblock]$Validation = $null
    )

    Write-Host "Testing: $Name" -ForegroundColor Cyan
    Write-Host "  URL: $Url" -ForegroundColor Gray

    try {
        $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 10 -ErrorAction Stop

        if ($Validation) {
            $validationResult = & $Validation $response
            if ($validationResult -eq $true) {
                Write-Host "  ${Green}[PASS]${Reset}" -ForegroundColor Green
                $script:testsPassed++
                return $response
            } else {
                Write-Host "  ${Red}[FAIL]${Reset} - Validation failed: $validationResult" -ForegroundColor Red
                $script:testsFailed++
                return $null
            }
        } else {
            Write-Host "  ${Green}[PASS]${Reset}" -ForegroundColor Green
            $script:testsPassed++
            return $response
        }
    } catch {
        Write-Host "  ${Red}[FAIL]${Reset} - $($_.Exception.Message)" -ForegroundColor Red
        $script:testsFailed++
        return $null
    }
}

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Claude Code Proxy - Health Tests" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Localhost connectivity
Write-Host "[1/4] Localhost Connectivity Test" -ForegroundColor Yellow
$healthResponse = Test-Endpoint -Name "Health Check (localhost)" -Url "http://localhost:8082/health" -Validation {
    param($r)
    if ($r.status -eq "healthy") { return $true } else { return "Status is not 'healthy'" }
}

if ($healthResponse) {
    Write-Host "  Status: $($healthResponse.status)" -ForegroundColor Gray
    if ($healthResponse.haiku) {
        $haikuProvider = "Anthropic"
        if ($healthResponse.haiku.provider_set) {
            $haikuProvider = "Z.AI (OK)"
        }
        Write-Host "  Haiku Model: $($healthResponse.haiku.model) -> $haikuProvider" -ForegroundColor Gray
    }
    if ($healthResponse.opus) {
        $opusProvider = "Anthropic"
        if ($healthResponse.opus.provider_set) {
            $opusProvider = "Alternative Provider (OK)"
        }
        Write-Host "  Opus Model: $($healthResponse.opus.model) -> $opusProvider" -ForegroundColor Gray
    }
    if ($healthResponse.sonnet) {
        $sonnetAuth = "API Key"
        if ($healthResponse.sonnet.uses_oauth) {
            $sonnetAuth = "OAuth"
        }

        $tokenStatus = "${Red}NOT FOUND${Reset}"
        if ($healthResponse.sonnet.oauth_token_available) {
            $tokenStatus = "${Green}Available${Reset}"
        }

        Write-Host "  Sonnet: $sonnetAuth (Token: $tokenStatus)" -ForegroundColor Gray

        if (-not $healthResponse.sonnet.oauth_token_available -and $healthResponse.sonnet.uses_oauth) {
            Write-Host "  ${Yellow}WARNING: OAuth token not found. Sonnet requests will fail.${Reset}" -ForegroundColor Yellow
        }
    }
}
Write-Host ""

# Test 2: Network accessibility
Write-Host "[2/4] Network Accessibility Test" -ForegroundColor Yellow

if ($NetworkIP) {
    $networkUrl = "http://${NetworkIP}:8082/health"
    Test-Endpoint -Name "Health Check (network)" -Url $networkUrl -Validation {
        param($r)
        if ($r.status -eq "healthy") { return $true } else { return "Status is not 'healthy'" }
    } | Out-Null
} else {
    # Try to detect local IP
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" } | Select-Object -First 1).IPAddress

    if ($localIP) {
        Write-Host "  Detected local IP: $localIP" -ForegroundColor Gray
        $networkUrl = "http://${localIP}:8082/health"
        Test-Endpoint -Name "Health Check (network)" -Url $networkUrl -Validation {
            param($r)
            if ($r.status -eq "healthy") { return $true } else { return "Status is not 'healthy'" }
        } | Out-Null
    } else {
        Write-Host "  ${Yellow}SKIP${Reset} - No network IP provided or detected" -ForegroundColor Yellow
        Write-Host "  To test network access, run: .\test-proxy.ps1 -NetworkIP <your-ip>" -ForegroundColor Gray
    }
}
Write-Host ""

# Test 3: Windows Firewall check
Write-Host "[3/4] Windows Firewall Configuration" -ForegroundColor Yellow
try {
    $firewallRule = Get-NetFirewallRule -DisplayName "Claude Code Proxy" -ErrorAction SilentlyContinue
    if ($firewallRule) {
        $enabled = $firewallRule.Enabled
        $action = $firewallRule.Action
        $direction = $firewallRule.Direction

        if ($enabled -eq "True" -and $action -eq "Allow" -and $direction -eq "Inbound") {
            Write-Host "  ${Green}[PASS]${Reset} - Firewall rule configured correctly" -ForegroundColor Green
            $testsPassed++
        } else {
            Write-Host "  ${Yellow}[WARNING]${Reset} - Firewall rule exists but may not be optimal" -ForegroundColor Yellow
            Write-Host "    Enabled: $enabled, Action: $action, Direction: $direction" -ForegroundColor Gray
        }
    } else {
        Write-Host "  ${Yellow}[WARNING]${Reset} - No firewall rule found for 'Claude Code Proxy'" -ForegroundColor Yellow
        Write-Host "  Run this command as Administrator to add firewall rule:" -ForegroundColor Gray
        Write-Host "    New-NetFirewallRule -DisplayName 'Claude Code Proxy' -Direction Inbound -LocalPort 8082 -Protocol TCP -Action Allow" -ForegroundColor DarkGray
    }
} catch {
    Write-Host "  ${Yellow}[WARNING]${Reset} - Could not check firewall rules (requires admin)" -ForegroundColor Yellow
}
Write-Host ""

# Test 4: Environment configuration
Write-Host "[4/4] Environment Configuration" -ForegroundColor Yellow

$ProxyRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $ProxyRoot ".env"

if (Test-Path $EnvFile) {
    Write-Host "  ${Green}[PASS]${Reset} - .env file exists" -ForegroundColor Green
    $testsPassed++

    if ($Verbose) {
        Write-Host "  Environment variables in .env:" -ForegroundColor Gray
        Get-Content $EnvFile | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]*)\s*=') {
                $name = $matches[1].Trim()
                Write-Host "    $name" -ForegroundColor DarkGray
            }
        }
    }
} else {
    Write-Host "  ${Red}[FAIL]${Reset} - .env file not found" -ForegroundColor Red
    Write-Host "  Create .env file at: $EnvFile" -ForegroundColor Gray
    Write-Host "  Use .env.example as a template" -ForegroundColor Gray
    $testsFailed++
}

# Check if Python is available
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "  ${Green}(OK)${Reset} Python: $pythonVersion" -ForegroundColor Gray
} catch {
    Write-Host "  ${Red}[FAIL]${Reset} Python not found in PATH" -ForegroundColor Red
}

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Test Summary" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Passed: ${Green}$testsPassed${Reset}" -ForegroundColor Green
Write-Host "  Failed: ${Red}$testsFailed${Reset}" -ForegroundColor Red

if ($testsFailed -eq 0) {
    Write-Host ""
    Write-Host "  ${Green}All tests passed!${Reset} Proxy is configured correctly." -ForegroundColor Green
    Write-Host ""
    exit 0
} else {
    Write-Host ""
    Write-Host "  ${Yellow}Some tests failed. Review the output above for details.${Reset}" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
