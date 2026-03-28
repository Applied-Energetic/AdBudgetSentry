param(
    [string]$CloudflaredExe = "C:\Cloudflared\cloudflared.exe",
    [string]$TokenFile = "",
    [string]$LogFile = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $TokenFile) {
    $TokenFile = Join-Path $RepoRoot "secrets\cloudflared-token.txt"
}
if (-not $LogFile) {
    $LogFile = Join-Path $RepoRoot "logs\cloudflared.log"
}

if (-not (Test-Path $CloudflaredExe)) {
    throw "cloudflared.exe not found: $CloudflaredExe"
}
if (-not (Test-Path $TokenFile)) {
    throw "Tunnel token file not found: $TokenFile"
}

$token = (Get-Content $TokenFile -ErrorAction Stop | Select-Object -First 1).Trim()
if (-not $token) {
    throw "Tunnel token is empty: $TokenFile"
}

$LogDir = Split-Path -Parent $LogFile
if ($LogDir) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

& $CloudflaredExe tunnel --no-autoupdate --loglevel info --logfile $LogFile run --token $token
