# Installation and Verification Guide

This guide helps you check if everything is installed correctly and provides installation commands if needed.

## Step 1: Check Node.js Installation

### Check if Node.js is installed:
```powershell
node --version
```

**Expected output:** `v16.x.x` or higher (e.g., `v20.11.0`)

**If not installed:**
1. Download from: https://nodejs.org/
2. Install the **LTS version** (recommended)
3. Restart PowerShell
4. Run `node --version` again

### Check if npm is installed:
```powershell
npm --version
```

**Expected output:** `8.x.x` or higher (e.g., `10.2.4`)

**If not installed:**
- npm comes with Node.js, so install Node.js first

## Step 2: Check @kiyo-e/claude-code-proxy Installation

### Check global installation:
```powershell
npm list -g @kiyo-e/claude-code-proxy
```

**Expected output:**
```
C:\Users\YourName\AppData\Roaming\npm
 @kiyo-e/claude-code-proxy@x.x.x
```

**If not installed:**
```powershell
npm install -g @kiyo-e/claude-code-proxy
```

**Alternative (no installation required):**
You can use `npx` to run the proxy without installing:
```powershell
npx @kiyo-e/claude-code-proxy
```

## Step 3: Check Python Installation (for Python proxy alternative)

### Check if Python is installed:
```powershell
python --version
```

**Expected output:** `Python 3.8.x` or higher

**If not installed:**
1. Download from: https://www.python.org/downloads/
2. Install Python 3.8 or higher
3. **Important:** Check "Add Python to PATH" during installation
4. Restart PowerShell
5. Run `python --version` again

### Check Python dependencies:
```powershell
cd C:\tools\claude-code-proxy
pip install -r requirements.txt
```

## Step 4: Verify Configuration Files

### Check .env file exists:
```powershell
cd C:\tools\claude-code-proxy\kiyo-e-proxy
Test-Path .env
```

**Expected output:** `True`

**If False:**
The .env file should have been created. Check if you're in the correct directory.

### View .env contents:
```powershell
cat .env
```

**Expected to see:**
- `OPENAI_API_BASE=https://api.enowdev.id`
- `OPENAI_API_KEY=enx_...`
- Model mappings (CLAUDE_37_SONNET, etc.)

## Step 5: Check Claude Code Settings

### Check if settings file exists:
```powershell
Test-Path "$env:USERPROFILE\.claude\settings.json"
```

**Expected output:** `True` (after running CONFIGURE-CLAUDE.ps1)

**If False:**
Run the configuration script:
```powershell
.\CONFIGURE-CLAUDE.ps1
```

### View settings contents:
```powershell
cat "$env:USERPROFILE\.claude\settings.json"
```

**Expected to see:**
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8080",
    "ANTHROPIC_API_KEY": "dummy-key-not-used",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "API_TIMEOUT_MS": "3000000"
  }
}
```

## Step 6: Test Network Connectivity

### Test EnowDev API directly:
```powershell
curl https://api.enowdev.id
```

**Expected:** Some response (not 404 or connection error)

### Test if port 8080 is available:
```powershell
netstat -an | findstr "8080"
```

**Expected:** No output (port is free)

**If port is in use:**
- Stop any existing proxy
- Or change PORT in .env to a different port (e.g., 8081)

## Step 7: Installation Summary

Run this script to check everything at once:

```powershell
Write-Host "Checking installation status..." -ForegroundColor Cyan
Write-Host ""

# Check Node.js
Write-Host "[1/7] Node.js:" -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "   Installed: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "   Not installed" -ForegroundColor Red
    Write-Host "   Install from: https://nodejs.org/" -ForegroundColor Yellow
}

# Check npm
Write-Host "[2/7] npm:" -ForegroundColor Yellow
try {
    $npmVersion = npm --version
    Write-Host "   Installed: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "   Not installed" -ForegroundColor Red
}

# Check @kiyo-e/claude-code-proxy
Write-Host "[3/7] @kiyo-e/claude-code-proxy:" -ForegroundColor Yellow
try {
    $proxyCheck = npm list -g @kiyo-e/claude-code-proxy 2>&1
    if ($proxyCheck -like "*@kiyo-e/claude-code-proxy*") {
        Write-Host "   Installed globally" -ForegroundColor Green
    } else {
        Write-Host "   Not installed (can use npx instead)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   Not installed (can use npx instead)" -ForegroundColor Yellow
}

# Check Python
Write-Host "[4/7] Python:" -ForegroundColor Yellow
try {
    $pythonVersion = python --version
    Write-Host "   Installed: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "   Not installed" -ForegroundColor Yellow
    Write-Host "   (Optional - only needed for Python proxy)" -ForegroundColor Gray
}

# Check .env file
Write-Host "[5/7] .env configuration:" -ForegroundColor Yellow
if (Test-Path "C:\tools\claude-code-proxy\kiyo-e-proxy\.env") {
    Write-Host "   Found" -ForegroundColor Green
} else {
    Write-Host "   Not found" -ForegroundColor Red
}

# Check Claude settings
Write-Host "[6/7] Claude Code settings:" -ForegroundColor Yellow
if (Test-Path "$env:USERPROFILE\.claude\settings.json") {
    Write-Host "   Found" -ForegroundColor Green
} else {
    Write-Host "   Not found (run CONFIGURE-CLAUDE.ps1)" -ForegroundColor Yellow
}

# Check port 8080
Write-Host "[7/7] Port 8080:" -ForegroundColor Yellow
$portCheck = netstat -an | findstr "8080"
if ($portCheck) {
    Write-Host "   In use (stop existing proxy first)" -ForegroundColor Yellow
} else {
    Write-Host "   Available" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installation check complete!" -ForegroundColor Cyan
```

Save this as `CHECK-INSTALLATION.ps1` and run it.

## Common Installation Issues

### Issue 1: Node.js not found

**Error:** `node : The term 'node' is not recognized...`

**Solution:**
1. Install Node.js from https://nodejs.org/
2. Restart PowerShell (important!)
3. Try again

### Issue 2: npm install fails

**Error:** `npm ERR! code EACCES` or permission errors

**Solution:**
```powershell
# Run PowerShell as Administrator
npm install -g @kiyo-e/claude-code-proxy
```

### Issue 3: Python not found

**Error:** `python : The term 'python' is not recognized...`

**Solution:**
1. Install Python from https://www.python.org/
2. Check "Add Python to PATH" during installation
3. Restart PowerShell
4. Try again

### Issue 4: Port 8080 already in use

**Error:** `Error: listen EADDRINUSE: address already in use :::8080`

**Solution:**
```powershell
# Find what's using port 8080
netstat -ano | findstr "8080"

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or change the port in .env
# PORT=8081
```

## Next Steps

Once everything is installed:

1. **Configure Claude Code:**
   ```powershell
   .\CONFIGURE-CLAUDE.ps1
   ```

2. **Start the proxy:**
   ```powershell
   .\START-PROXY.ps1
   ```

3. **Test the connection:**
   ```powershell
   .\TEST-PROXY.ps1
   ```

4. **Use Claude Code normally**

## Getting Help

If you encounter issues:

1. Check this installation guide
2. Read SETUP-INSTRUCTIONS.md for detailed troubleshooting
3. Try the Python proxy alternative (already configured)
4. Check the proxy logs for error messages

## Summary

 **Node.js**: Required for Node.js proxy  
 **npm**: Comes with Node.js  
 **@kiyo-e/claude-code-proxy**: Install globally or use npx  
 **Python**: Optional (for Python proxy alternative)  
 **.env**: Configuration file (already created)  
 **Claude settings**: Run CONFIGURE-CLAUDE.ps1  
