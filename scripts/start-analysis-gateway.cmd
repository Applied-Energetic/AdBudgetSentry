@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-analysis-gateway.ps1"
