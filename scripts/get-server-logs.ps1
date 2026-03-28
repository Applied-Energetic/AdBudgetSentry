param(
    [ValidateSet("gateway-stdout", "gateway-stderr", "cloudflared", "cloudflared-stdout", "cloudflared-stderr")]
    [string]$Component = "gateway-stdout",
    [int]$Tail = 80,
    [string]$Pattern = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogMap = @{
    "gateway-stdout" = Join-Path $RepoRoot "logs\analysis-gateway.stdout.log"
    "gateway-stderr" = Join-Path $RepoRoot "logs\analysis-gateway.stderr.log"
    "cloudflared" = Join-Path $RepoRoot "logs\cloudflared.log"
    "cloudflared-stdout" = Join-Path $RepoRoot "logs\cloudflared.stdout.log"
    "cloudflared-stderr" = Join-Path $RepoRoot "logs\cloudflared.stderr.log"
}

$Path = $LogMap[$Component]
if (-not (Test-Path $Path)) {
    throw "Log file not found: $Path"
}

$Lines = Get-Content -Path $Path -Tail $Tail -Encoding UTF8
if ($Pattern) {
    $Lines = $Lines | Where-Object { $_ -match $Pattern }
}

$Lines
