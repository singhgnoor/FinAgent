$BackendPort = 5174
$FrontendPort = 5173
$BackendUrl = "http://localhost:$BackendPort/api/v1/health"
$StartupTimeout = 90

# Kill any leftovers on our ports
Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 2

Write-Host "Starting backend on port $BackendPort..." -ForegroundColor Cyan
# Load OPENAI_API_KEY from .env if not already set
if (-not $env:OPENAI_API_KEY) {
    $envLine = Get-Content (Join-Path $PSScriptRoot ".env") -ErrorAction SilentlyContinue | Where-Object { $_ -match "^OPENAI_API_KEY=(.+)$" }
    if ($envLine) {
        $env:OPENAI_API_KEY = $Matches[1]
    }
}
if (-not $env:OPENAI_API_KEY) {
    Write-Host "WARNING: OPENAI_API_KEY not set. Set it in .env or as an environment variable." -ForegroundColor Yellow
}
$backend = Start-Process -NoNewWindow -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port $BackendPort --log-level error" -PassThru

Write-Host "Waiting for backend..." -ForegroundColor Yellow
$ready = $false
$startTime = Get-Date
while (-not $ready -and ((Get-Date) - $startTime).TotalSeconds -lt $StartupTimeout) {
    try {
        $r = Invoke-WebRequest -Uri $BackendUrl -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $ready = $true }
    } catch {}
    if (-not $ready) { Start-Sleep 3 }
}

$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds)

if (-not $ready) {
    Write-Host "Backend failed to start within ${StartupTimeout}s" -ForegroundColor Red
    $backend.Kill()
    exit 1
}

Write-Host "Backend ready (${elapsed}s)" -ForegroundColor Green

Write-Host "Starting frontend on port $FrontendPort..." -ForegroundColor Cyan
$frontend = Start-Process -NoNewWindow -FilePath "npx.cmd" -ArgumentList "vite --port $FrontendPort" -WorkingDirectory (Join-Path $PSScriptRoot "frontend") -PassThru

Start-Process "http://localhost:$FrontendPort"

Write-Host "`nBackend : http://localhost:$BackendPort" -ForegroundColor Green
Write-Host "Frontend: http://localhost:$FrontendPort" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop both servers`n" -ForegroundColor Gray

# Wait for either process to exit, then clean up
try {
    while (-not $backend.HasExited -and -not $frontend.HasExited) { Start-Sleep 2 }
} finally {
    if (-not $backend.HasExited) { $backend.Kill() }
    if (-not $frontend.HasExited) { $frontend.Kill() }
}
