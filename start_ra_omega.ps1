param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Edit .env to add real provider keys." -ForegroundColor Yellow
}

if (-not $env:ATLAS_DISABLE_AUTH) {
    $env:ATLAS_DISABLE_AUTH = "true"
}

Write-Host "Starting R.A. Omega on http://127.0.0.1:$Port/option1" -ForegroundColor Cyan
python -m uvicorn api_server:app --host 0.0.0.0 --port $Port --reload
