# Cloudflare Tunnel Setup

This directory contains scripts to manage a Cloudflare tunnel for the proxy server.

## Quick Start

### Windows

```bash
start-tunnel.bat
```

### Linux/VPS

```bash
chmod +x start-tunnel.sh
./start-tunnel.sh start
```

## Scripts

### Windows: `start-tunnel.bat`

- Kills any existing cloudflared processes
- Starts a new tunnel in the background
- Extracts and saves the tunnel URL to `TUNNEL_URL.txt`
- Displays the active tunnel URL

### Linux/VPS: `start-tunnel.sh`

- Auto-downloads cloudflared if not present
- Manages tunnel lifecycle (start/stop/restart/status)
- Saves tunnel URL for easy access

## Usage

### Start Tunnel

**Windows:**

```bash
start-tunnel.bat
```

**Linux:**

```bash
./start-tunnel.sh start
```

### Check Status

**Windows:**

```bash
tasklist | findstr cloudflared
curl https://your-tunnel-url.trycloudflare.com/health
```

**Linux:**

```bash
./start-tunnel.sh status
```

### Stop Tunnel

**Windows:**

```bash
taskkill //F //IM cloudflared.exe
```

**Linux:**

```bash
./start-tunnel.sh stop
```

### Restart Tunnel

**Linux:**

```bash
./start-tunnel.sh restart
```

## Files

- `TUNNEL_URL.txt` - Contains the current tunnel URL
- `tunnel.log` - Cloudflared log file (JSON format)
- `cloudflared.exe` (Windows) or `cloudflared` (Linux) - Cloudflare tunnel binary

## Automated VPS Deployment

You can use the provided daemon scripts to automatically set up the proxy and tunnel as services.

### 1. Install Proxy as Service

```bash
sudo bash scripts/install-daemon.sh
```

### 2. Manual Systemd Service (Optional)

If you prefer to manually configure the tunnel, create a systemd service:

```bash
sudo nano /etc/systemd/system/cloudflare-tunnel.service
```

Add:

```ini
[Unit]
Description=Cloudflare Tunnel for Claude Proxy
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/claude-code-proxy
ExecStart=/path/to/claude-code-proxy/cloudflared tunnel --url http://localhost:8082 --logfile tunnel.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable cloudflare-tunnel
sudo systemctl start cloudflare-tunnel
```

## Troubleshooting

### Tunnel not connecting

- Check if proxy is running: `curl http://localhost:8082/health`
- Check tunnel logs: `tail -f tunnel.log`
- Restart tunnel: Kill process and restart

### URL not extracted

- Wait 15-20 seconds for tunnel to fully establish
- Check `tunnel.log` for errors
- Manually extract URL: `grep -o "https://.*\.trycloudflare\.com" tunnel.log | tail -1`

### Connection errors

- Ensure port 8082 is not blocked by firewall
- Check if proxy server is running
- Verify network connectivity

## Notes

- Free Cloudflare tunnels (trycloudflare.com) have no uptime guarantee
- URLs change each time you restart the tunnel
- For production, consider using a named tunnel with a Cloudflare account
- The tunnel automatically routes to `http://localhost:8082`
