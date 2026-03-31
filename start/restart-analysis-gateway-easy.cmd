@echo off
setlocal
set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%..\scripts"
echo ========================================
echo STEP 1: Stopping all existing processes...
echo ========================================
powershell -NoProfile -ExecutionPolicy Bypass -File "stop-analysis-gateway-background.ps1"

timeout /t 2 /nobreak > nul

echo ========================================
echo STEP 2: Starting Analysis Gateway...
echo ========================================
powershell -NoProfile -ExecutionPolicy Bypass -File "start-analysis-gateway.ps1"
popd
pause
