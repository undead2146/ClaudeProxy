@echo off
echo Starting Cloudflare Tunnel in background...
echo.

REM Kill any existing cloudflared processes
taskkill //F //IM cloudflared.exe >nul 2>&1

REM Wait a moment for processes to fully terminate
timeout /t 2 /nobreak >nul

REM Start the tunnel in background
echo Starting new tunnel connection...
start /B cloudflared.exe tunnel --url http://localhost:8082 --logfile tunnel.log

REM Wait for tunnel to establish
echo Waiting for tunnel to establish (10 seconds)...
timeout /t 10 /nobreak >nul

REM Extract URL from log file
echo Extracting tunnel URL...
findstr /C:"https://" tunnel.log | findstr /C:"trycloudflare.com" > TUNNEL_URL.txt

if exist TUNNEL_URL.txt (
    echo.
    echo ========================================
    echo Tunnel is ACTIVE!
    echo ========================================
    type TUNNEL_URL.txt
    echo ========================================
    echo.
    echo Tunnel is running in background.
    echo Log file: tunnel.log
    echo To stop: taskkill //F //IM cloudflared.exe
) else (
    echo.
    echo WARNING: Could not extract tunnel URL from log.
    echo Check tunnel.log for details.
)
