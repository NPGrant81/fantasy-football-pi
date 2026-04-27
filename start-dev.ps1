$ErrorActionPreference = "Stop"

$ROOT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_HOST = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "127.0.0.1" }
$BACKEND_PORT = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$FRONTEND_PORT = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }
# Always probe 127.0.0.1 so the health check works even when BACKEND_HOST is 0.0.0.0
$BACKEND_HEALTH_HOST = if ($env:BACKEND_HEALTH_HOST) { $env:BACKEND_HEALTH_HOST } else { "127.0.0.1" }
$BACKEND_HEALTH_URL = "http://$BACKEND_HEALTH_HOST`:$BACKEND_PORT/health"
$BACKEND_LOG = Join-Path $ROOT_DIR ".dev-backend.log"
$BACKEND_PROCESS = $null
$BACKEND_PYTHON = $null

function Log([string]$message) {
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $message"
}

function Require-Command([string]$name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Log "Missing required command: $name"
        exit 1
    }
}

function Test-Health([string]$url) {
    try {
        # -UseBasicParsing is not supported in PowerShell 7+; use Invoke-WebRequest without it
        $resp = Invoke-WebRequest -Uri $url -TimeoutSec 2
        return $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300
    } catch {
        return $false
    }
}

function Test-PortInUse([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-BackendIfOwned {
    if ($null -ne $BACKEND_PROCESS -and -not $BACKEND_PROCESS.HasExited) {
        Log "Stopping backend (PID $($BACKEND_PROCESS.Id))"
        try {
            Stop-Process -Id $BACKEND_PROCESS.Id -Force -ErrorAction SilentlyContinue
        } catch {
            # no-op
        }
    }
}

function Resolve-BackendPython {
    $candidates = @(
        (Join-Path $ROOT_DIR "backend/venv/Scripts/python.exe"),
        (Join-Path $ROOT_DIR ".venv/Scripts/python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            & $candidate -c "import fastapi, uvicorn" *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
    }

    if (Get-Command "python" -ErrorAction SilentlyContinue) {
        & python -c "import fastapi, uvicorn" *> $null
        if ($LASTEXITCODE -eq 0) {
            return "python"
        }
    }

    Log "Could not find a Python interpreter with fastapi and uvicorn installed."
    Log "Install backend dependencies in backend/venv or .venv, then retry."
    exit 1
}

Require-Command "npm"

Set-Location $ROOT_DIR

if (-not (Test-Path (Join-Path $ROOT_DIR "frontend"))) {
    Log "frontend directory not found. Run this script from the repository root."
    exit 1
}

$backendEnv = Join-Path $ROOT_DIR "backend/.env"
$backendEnvExample = Join-Path $ROOT_DIR "backend/.env.example"
if (-not (Test-Path $backendEnv)) {
    if (-not (Test-Path $backendEnvExample)) {
        Log "backend/.env.example not found. Cannot bootstrap backend/.env."
        exit 1
    }
    Log "backend/.env not found. Creating it from backend/.env.example."
    Copy-Item -Path $backendEnvExample -Destination $backendEnv
}

$BACKEND_PYTHON = Resolve-BackendPython
Log "Using backend Python: $BACKEND_PYTHON"

if (Test-PortInUse ([int]$FRONTEND_PORT)) {
    Log "Frontend port $FRONTEND_PORT is already in use."
    Log "Stop the existing frontend process or set FRONTEND_PORT to a different value."
    exit 1
}

if (Get-Command "pg_isready" -ErrorAction SilentlyContinue) {
    try {
        & pg_isready -h 127.0.0.1 -p 5432 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Log "Postgres is reachable on 127.0.0.1:5432"
        } else {
            Log "Postgres is not reachable on 127.0.0.1:5432."
            Log "Backend health requires DB connectivity, so startup will likely fail until Postgres is available."
        }
    } catch {
        Log "Postgres check failed. Backend health requires DB connectivity, so startup will likely fail until Postgres is available."
    }
} else {
    Log "pg_isready not found; skipping Postgres readiness check."
}

try {
    if (Test-Health $BACKEND_HEALTH_URL) {
        Log "Backend already healthy at $BACKEND_HEALTH_URL"
    } else {
        if (Test-PortInUse ([int]$BACKEND_PORT)) {
            Log "Port $BACKEND_PORT is already in use, but $BACKEND_HEALTH_URL is not healthy."
            Log "Stop the process using port $BACKEND_PORT or set BACKEND_PORT to a different value."
            exit 1
        }

        Log "Starting backend on $BACKEND_HOST`:$BACKEND_PORT"
        $BACKEND_PROCESS = Start-Process -FilePath $BACKEND_PYTHON -ArgumentList @(
            "-m", "uvicorn", "backend.main:app", "--host", "$BACKEND_HOST", "--port", "$BACKEND_PORT", "--reload"
        ) -RedirectStandardOutput $BACKEND_LOG -RedirectStandardError $BACKEND_LOG -PassThru

        Log "Backend PID: $($BACKEND_PROCESS.Id) (logs: $BACKEND_LOG)"

        for ($i = 1; $i -le 60; $i++) {
            if (Test-Health $BACKEND_HEALTH_URL) {
                Log "Backend is healthy"
                break
            }

            if ($BACKEND_PROCESS.HasExited) {
                Log "Backend exited before becoming healthy. Last log lines:"
                if (Test-Path $BACKEND_LOG) {
                    Get-Content $BACKEND_LOG -Tail 40
                }
                exit 1
            }

            Start-Sleep -Seconds 1

            if ($i -eq 60) {
                Log "Timed out waiting for backend health at $BACKEND_HEALTH_URL"
                if (Test-Path $BACKEND_LOG) {
                    Get-Content $BACKEND_LOG -Tail 40
                }
                exit 1
            }
        }
    }

    Log "Starting frontend on port $FRONTEND_PORT"
    Set-Location (Join-Path $ROOT_DIR "frontend")
    & npm run dev -- --port "$FRONTEND_PORT" --strictPort
}
finally {
    Stop-BackendIfOwned
}
