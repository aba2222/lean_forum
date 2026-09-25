@echo off
REM 双击即可启动开发服务器（转交给 dev.ps1）。
REM 需要自定义端口或先跑迁移时，请直接用 PowerShell 调用 dev.ps1。
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
pause
