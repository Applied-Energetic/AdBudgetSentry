param()

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $RepoRoot "run"
$PidFile = Join-Path $RunDir "analysis-gateway.pid"

# 1. 强制清理任何仍然占用 8787 端口的 python 进程
Write-Host "Checking for processes on port 8787..."
$portProcesses = Get-NetTCPConnection -LocalPort 8787 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($p in $portProcesses) {
    if ($p) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Stopping process $($proc.ProcessName) (PID $p) on port 8787..."
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    }
}

# 2. 如果 PID 文件存在且进程还在运行，也清理掉
if (Test-Path $PidFile) {
    $rawPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($rawPid) {
        $process = Get-Process -Id $rawPid -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Stopping process from PID file: $rawPid"
            Stop-Process -Id $rawPid -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Write-Host "Cleanup complete."
