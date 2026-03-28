param(
    [string]$TaskName = "AdBudgetSentry-AnalysisGateway",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$EnsureDeps
)

$ErrorActionPreference = "Stop"

$Starter = Join-Path $PSScriptRoot "start-analysis-gateway-background.ps1"
$args = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-WindowStyle", "Hidden",
    "-File", "`"$Starter`"",
    "-HostAddress", $HostAddress,
    "-Port", "$Port",
    "-ForceRestart"
)
if ($EnsureDeps) {
    $args += "-EnsureDeps"
}

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
    -Description "Start AdBudgetSentry Analysis Gateway in background at Windows startup" `
    -Force | Out-Null

Write-Host "Scheduled task installed: $TaskName"
Write-Host "You can start it immediately with: schtasks /Run /TN `"$TaskName`""
