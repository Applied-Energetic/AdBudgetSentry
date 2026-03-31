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

$RunDir = Join-Path $RepoRoot "run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$PidFile = Join-Path $RunDir "analysis-gateway.pid"

Write-Host "Starting Analysis Gateway on http://$HostAddress`:$Port"
Push-Location $GatewayDir

# 启动进程并保存 PID
$process = Start-Process -FilePath $PythonExe -ArgumentList "app.py" -NoNewWindow -PassThru
$process.Id | Out-File $PidFile -Encoding utf8
Write-Host "Process started with PID: $($process.Id)"

# 等待进程退出
$process.WaitForExit()
Pop-Location
