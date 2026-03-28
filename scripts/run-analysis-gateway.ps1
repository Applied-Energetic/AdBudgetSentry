param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$EnsureDeps
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
    Push-Location $GatewayDir
    python -m venv .venv
    Pop-Location
    $EnsureDeps = $true
}

if (-not (Test-Path $PythonExe)) {
    throw "Python virtual environment is incomplete: $PythonExe"
}

if (-not (Test-Path $ConfigFile) -and (Test-Path $ConfigExample)) {
    Copy-Item $ConfigExample $ConfigFile
}

if ($EnsureDeps) {
    & $PythonExe -m pip install -r $Requirements
}

$env:ADBUDGET_HOST = $HostAddress
$env:ADBUDGET_PORT = "$Port"
$env:ADBUDGET_DB_PATH = $DbPath

Push-Location $GatewayDir
try {
    & $PythonExe app.py
} finally {
    Pop-Location
}
