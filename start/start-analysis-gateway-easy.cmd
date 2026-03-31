@echo off
setlocal
set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%..\scripts"
powershell -NoProfile -ExecutionPolicy Bypass -File "start-analysis-gateway.ps1"
popd
pause
