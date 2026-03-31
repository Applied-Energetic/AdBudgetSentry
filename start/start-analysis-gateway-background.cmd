@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%..\scripts\start-analysis-gateway-background.ps1" -EnsureDeps
