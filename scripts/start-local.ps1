# NOVARA — beginner-friendly local start (Windows PowerShell).
# No PostgreSQL, Redis, Docker or hosted account required.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root "apps\api"
$venv = Join-Path $root ".venv"
$pythonExe = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
  Write-Host "Creating a local Python environment..."
  python -m venv $venv
}

# pip writes ordinary warnings to stderr; PowerShell 5 treats that as a
# terminating error when ErrorActionPreference is Stop. Check exit codes
# explicitly instead of letting a warning abort first-run startup.
$ErrorActionPreference = "Continue"
& $pythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $pythonExe -m pip install -e "$api[dev]"
if ($LASTEXITCODE -ne 0) { throw "dependency installation failed" }

Write-Host ""
Write-Host "NOVARA is starting."
Write-Host "Open http://localhost:8000 in your browser."
Write-Host "Finish the first-run setup, then use the dashboard."
Write-Host "Press Ctrl+C to stop."
Write-Host ""

$env:PYTHONPATH = $api
& $pythonExe -m uvicorn novara_core.main:app --app-dir $api --host 127.0.0.1 --port 8000
