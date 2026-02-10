@echo off
REM Cloudflare Tunnel Startup Script for Windows
REM This script manages the Cloudflare tunnel for the proxy server

set TUNNEL_LOG=tunnel.log
set TUNNEL_URL_FILE=TUNNEL_URL.txt
set PROXY_PORT=8082

echo ==========================================
echo Cloudflare Tunnel Manager
echo ==========================================
echo.

REM Kill any existing cloudflared processes
echo Stopping any existing cloudflared processes...
taskkill //F //IM cloudflared.exe >nul 2>&1

REM Wait for processes to fully terminate
timeout /t 2 /nobreak >nul

echo Starting Cloudflare tunnel...
echo Proxy URL: http://localhost:%PROXY_PORT%
echo.

REM Start tunnel in background
start /B cloudflared.exe tunnel --url http://localhost:%PROXY_PORT% --logfile %TUNNEL_LOG%

REM Wait for tunnel to establish
echo Waiting for tunnel to establish (15 seconds)...
timeout /t 15 /nobreak >nul

REM Extract URL from log file
for /f "tokens=*" %%i in ('findstr /C:"https://" %TUNNEL_LOG% ^| findstr /C:"trycloudflare.com" ^| findstr /V /C:"INF" ^| findstr /V /C:"message"') do set TUNNEL_LINE=%%i

REM Try to extract just the URL from JSON format
for /f "tokens=2 delims:|" %%a in ('findstr /C:"|  https://" %TUNNEL_LOG%') do (
    set TUNNEL_URL=%%a
    goto :found_url
)

REM If not found in box format, try JSON format
for /f "tokens=*" %%i in ('powershell -Command "Get-Content %TUNNEL_LOG% | Select-String -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | ForEach-Object { $_.Matches.Value } | Select-Object -Last 1"') do set TUNNEL_URL=%%i

:found_url
REM Clean up the URL (remove extra spaces)
set TUNNEL_URL=%TUNNEL_URL: =%

if defined TUNNEL_URL (
    echo %TUNNEL_URL% > %TUNNEL_URL_FILE%
    echo.
    echo ==========================================
    echo  TUNNEL IS ACTIVE!
    echo ==========================================
    echo URL: %TUNNEL_URL%
    echo ==========================================
    echo.
    echo Tunnel is running in background.
    echo Log file: %TUNNEL_LOG%
    echo URL file: %TUNNEL_URL_FILE%
    echo.
    echo To stop: taskkill //F //IM cloudflared.exe
    echo To check status: curl %TUNNEL_URL%/health
) else (
    echo.
    echo WARNING: Could not extract tunnel URL from log.
    echo Check %TUNNEL_LOG% for details.
)

echo.
pause
