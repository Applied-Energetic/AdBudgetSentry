param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$GatewayDir = Join-Path $RepoRoot "code\analysis_gateway"
$VenvDir = Join-Path $GatewayDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $GatewayDir "requirements.txt"
$ConfigExample = Join-Path $GatewayDir "config.example.json"
$ConfigFile = Join-Path $GatewayDir "config.json"
$DbPath = Join-Path $RepoRoot "data\app.db"

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment at $VenvDir"
    Push-Location $GatewayDir
    python -m venv .venv
    Pop-Location
}

if (-not (Test-Path $PythonExe)) {
    throw "Python virtual environment is incomplete: $PythonExe"
}

if (-not (Test-Path $ConfigFile) -and (Test-Path $ConfigExample)) {
    Copy-Item $ConfigExample $ConfigFile
    Write-Host "Created config.json from config.example.json"
}

Write-Host "Installing dependencies from $Requirements"
& $PythonExe -m pip install -r $Requirements

$env:ADBUDGET_HOST = $HostAddress
$env:ADBUDGET_PORT = "$Port"
$env:ADBUDGET_DB_PATH = $DbPath

Write-Host "Starting Analysis Gateway on http://$HostAddress`:$Port"
Push-Location $GatewayDir
& $PythonExe app.py
Pop-Location
