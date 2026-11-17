# Start the disposable LabAdda test copy on http://127.0.0.1:8000/ (Ctrl+C stops it).
#   powershell -ExecutionPolicy Bypass -File scripts\windows\serve-dev.ps1
param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..\backend")
$env:LABADDA_ENV = "development"
Write-Host "Open http://127.0.0.1:$Port/ and sign in as asha with password fixture-pass-123"
& "..\.venv\Scripts\python.exe" -m labadda.cli serve --port $Port
exit $LASTEXITCODE
