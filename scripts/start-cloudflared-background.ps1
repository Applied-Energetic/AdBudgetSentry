param(
    [string]$CloudflaredExe = "C:\Cloudflared\cloudflared.exe",
    [string]$TokenFile = "",
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogsDir = Join-Path $RepoRoot "logs"
$RunDir = Join-Path $RepoRoot "run"
$PidFile = Join-Path $RunDir "cloudflared.pid"
$StdoutLog = Join-Path $LogsDir "cloudflared.stdout.log"
$StderrLog = Join-Path $LogsDir "cloudflared.stderr.log"
$CloudflaredLog = Join-Path $LogsDir "cloudflared.log"
$Runner = Join-Path $PSScriptRoot "run-cloudflared.ps1"

if (-not $TokenFile) {
    $TokenFile = Join-Path $RepoRoot "secrets\cloudflared-token.txt"
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

if (Test-Path $PidFile) {
    $existingPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) {
        if (-not $ForceRestart) {
            Write-Host "cloudflared already running with PID $existingPid"
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
    "-CloudflaredExe", "`"$CloudflaredExe`"",
    "-TokenFile", "`"$TokenFile`"",
    "-LogFile", "`"$CloudflaredLog`""
)

$process = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $argList `
    -WindowStyle Hidden `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $StdoutLog `
    -RedirectStandardError $StderrLog `
    -PassThru

Set-Content -Path $PidFile -Value $process.Id -Encoding ASCII
Write-Host "cloudflared started in background. PID=$($process.Id)"
