param(
    [string]$TaskName = "AdBudgetSentry-Cloudflared",
    [string]$CloudflaredExe = "C:\Cloudflared\cloudflared.exe",
    [string]$TokenFile = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $TokenFile) {
    $TokenFile = Join-Path $RepoRoot "secrets\cloudflared-token.txt"
}

$Starter = Join-Path $PSScriptRoot "start-cloudflared-background.ps1"
$args = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-WindowStyle", "Hidden",
    "-File", "`"$Starter`"",
    "-CloudflaredExe", "`"$CloudflaredExe`"",
    "-TokenFile", "`"$TokenFile`"",
    "-ForceRestart"
)

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($args -join " ")
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Start cloudflared tunnel for AdBudgetSentry in background at Windows startup" `
    -Force | Out-Null

Write-Host "Scheduled task installed: $TaskName"
Write-Host "You can start it immediately with: schtasks /Run /TN `"$TaskName`""
