param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$ForceRestart,
    [switch]$EnsureDeps
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogsDir = Join-Path $RepoRoot "logs"
$RunDir = Join-Path $RepoRoot "run"
$PidFile = Join-Path $RunDir "analysis-gateway.pid"
$StdoutLog = Join-Path $LogsDir "analysis-gateway.stdout.log"
$StderrLog = Join-Path $LogsDir "analysis-gateway.stderr.log"
$Runner = Join-Path $PSScriptRoot "run-analysis-gateway.ps1"

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

if (Test-Path $PidFile) {
    $existingPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) {
        if (-not $ForceRestart) {
            Write-Host "Analysis Gateway already running with PID $existingPid"
            exit 0
        }
        Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

$argList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$Runner`"",
    "-HostAddress", $HostAddress,
    "-Port", "$Port"
)
if ($EnsureDeps) {
    $argList += "-EnsureDeps"
}

$process = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $argList `
    -WindowStyle Hidden `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $StdoutLog `
    -RedirectStandardError $StderrLog `
    -PassThru

Set-Content -Path $PidFile -Value $process.Id -Encoding ASCII
Write-Host "Analysis Gateway started in background. PID=$($process.Id)"
