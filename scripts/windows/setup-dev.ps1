# One-time setup of a disposable LabAdda test copy on Windows 10/11 (fictional data only).
# Needs Python 3.12, Node 22 and PostgreSQL 16 for Windows, with the databases from
# docs/development/windows-testing.md already created. Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\setup-dev.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

function Invoke-Step([string]$Label, [scriptblock]$Command) {
    Write-Host "== $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit code $LASTEXITCODE)" }
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-Step "Create the Python 3.12 environment" { py -3.12 -m venv .venv }
}
$python = ".venv\Scripts\python.exe"
Invoke-Step "Install locked Python packages" { & $python -m pip install -q -r backend\requirements.lock }
Invoke-Step "Install LabAdda in editable mode" { & $python -m pip install -q --no-deps -e backend }
Invoke-Step "Install frontend packages" { npm ci --prefix frontend --no-audit --no-fund }
Invoke-Step "Build the frontend" { npm run --prefix frontend build }

$env:LABADDA_ENV = "development"
Push-Location backend
try {
    Invoke-Step "Apply database migrations" { & "..\$python" -m labadda.cli migrate }
    Invoke-Step "Load the fictional fixture (erases labadda_dev)" { & "..\$python" -m labadda.cli seed --reset }
} finally {
    Pop-Location
}
Write-Host "Setup finished. Start the server with: scripts\windows\serve-dev.ps1"
