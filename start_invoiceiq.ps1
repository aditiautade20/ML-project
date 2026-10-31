# ==============================================================================
# InvoiceIQ — Unified Local Development Launcher
# Starts both FastAPI Backend and React (Vite) Frontend in dedicated windows.
# ==============================================================================

$ErrorActionPreference = "Stop"

# Determine script root directory
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$BackendDir  = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   InvoiceIQ - Application Startup Manager        " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------------------
# 1. Dependency & Environment Checks
# ------------------------------------------------------------------------------
Write-Host "[1/4] Verifying prerequisites and environments..." -ForegroundColor Yellow

# Check Backend Virtual Environment
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Backend virtual environment not found!" -ForegroundColor Red
    Write-Host "Expected path: $PythonExe" -ForegroundColor Red
    Write-Host "Please set up the virtual environment first:" -ForegroundColor Yellow
    Write-Host "  cd `"$BackendDir`"" -ForegroundColor White
    Write-Host "  python -m venv .venv" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\pip.exe install -r requirements.txt" -ForegroundColor White
    exit 1
}

# Check Frontend Dependencies
$NodeModulesDir = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $NodeModulesDir)) {
    Write-Host "ERROR: Frontend node_modules directory not found!" -ForegroundColor Red
    Write-Host "Please install frontend dependencies first:" -ForegroundColor Yellow
    Write-Host "  cd `"$FrontendDir`"" -ForegroundColor White
    Write-Host "  npm.cmd install" -ForegroundColor White
    exit 1
}

# Ensure Backend .env exists
$BackendEnv = Join-Path $BackendDir ".env"
$BackendEnvExample = Join-Path $BackendDir ".env.example"
if (-not (Test-Path $BackendEnv) -and (Test-Path $BackendEnvExample)) {
    Copy-Item $BackendEnvExample $BackendEnv
    Write-Host "  Created backend/.env from .env.example" -ForegroundColor DarkGray
}

# Ensure Frontend .env exists
$FrontendEnv = Join-Path $FrontendDir ".env"
$FrontendEnvExample = Join-Path $FrontendDir ".env.example"
if (-not (Test-Path $FrontendEnv) -and (Test-Path $FrontendEnvExample)) {
    Copy-Item $FrontendEnvExample $FrontendEnv
    Write-Host "  Created frontend/.env from .env.example" -ForegroundColor DarkGray
}

# Check Database & Apply Migrations safely (preserves existing data, applies pending updates)
$AlembicExe = Join-Path $BackendDir ".venv\Scripts\alembic.exe"
if (Test-Path $AlembicExe) {
    Write-Host "  Checking and safely applying any pending database migrations..." -ForegroundColor DarkGray
    Push-Location $BackendDir
    try {
        & $AlembicExe upgrade head
    } finally {
        Pop-Location
    }
}

Write-Host "  Prerequisites verified successfully." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 2. Launch FastAPI Backend in a Separate Window
# ------------------------------------------------------------------------------
Write-Host "[2/4] Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Yellow

$BackendCmd = @"
`$host.UI.RawUI.WindowTitle = 'InvoiceIQ - FastAPI Backend (Port 8000)'
Set-Location -LiteralPath '$BackendDir'
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '   InvoiceIQ Backend (FastAPI + Uvicorn)          ' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host 'API URL:     http://127.0.0.1:8000' -ForegroundColor Green
Write-Host 'Docs (SWAG): http://127.0.0.1:8000/docs' -ForegroundColor Green
Write-Host 'Press Ctrl + C to stop the backend server.' -ForegroundColor Yellow
Write-Host ''
& '.\.venv\Scripts\python.exe' run.py
"@

Start-Process powershell.exe -ArgumentList "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", $BackendCmd

# ------------------------------------------------------------------------------
# 3. Launch React / Vite Frontend in a Separate Window
# ------------------------------------------------------------------------------
Write-Host "[3/4] Starting React/Vite frontend on http://127.0.0.1:5173..." -ForegroundColor Yellow

$FrontendCmd = @"
`$host.UI.RawUI.WindowTitle = 'InvoiceIQ - Vite Frontend (Port 5173)'
Set-Location -LiteralPath '$FrontendDir'
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '   InvoiceIQ Frontend (React + Vite)              ' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host 'Website URL: http://127.0.0.1:5173' -ForegroundColor Green
Write-Host 'Press Ctrl + C to stop the frontend server.' -ForegroundColor Yellow
Write-Host ''
npm.cmd run dev
"@

Start-Process powershell.exe -ArgumentList "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", $FrontendCmd

# ------------------------------------------------------------------------------
# 4. Summary & Instructions
# ------------------------------------------------------------------------------
Write-Host "[4/4] Both servers have been launched in separate terminal windows!" -ForegroundColor Green
Write-Host ""
Write-Host "Local Application URLs:" -ForegroundColor White
Write-Host "  * Website (Frontend):      http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "  * API Base (Backend):      http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "  * Interactive Swagger UI:  http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  * Alternative ReDoc:       http://127.0.0.1:8000/redoc" -ForegroundColor Cyan
Write-Host ""
Write-Host "Stopping the Servers:" -ForegroundColor White
Write-Host "  * Simply close the two newly opened PowerShell terminal windows." -ForegroundColor Yellow
Write-Host "  * Or press Ctrl + C in each window to stop the server process." -ForegroundColor Yellow
Write-Host ""
