# InvoiceIQ - Demo Data Seeder Utility
# Populates or resets the isolated showcase demo account (demo@invoiceiq.local / DemoUser123!)
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Python virtual environment not found at $VenvPython. Please set up the backend virtual environment first."
    exit 1
}

Push-Location $BackendDir
try {
    if ($Clean) {
        Write-Host "Cleaning up InvoiceIQ demo data..." -ForegroundColor Yellow
        & $VenvPython -m app.demo_seed --clean
    } else {
        Write-Host "Seeding InvoiceIQ demo showcase data..." -ForegroundColor Cyan
        & $VenvPython -m app.demo_seed --seed
    }
} finally {
    Pop-Location
}
