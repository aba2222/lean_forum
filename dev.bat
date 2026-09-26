@echo off
REM 双击就能跑：转交给 dev.ps1，把环境缺的东西补上再启动开发服务器。
REM
REM 需要自定义端口、建后台账号，或者只想跑测试时，直接在 PowerShell 里用 dev.ps1：
REM     .\dev.ps1 -Port 9000
REM     .\dev.ps1 -Superuser
REM     .\dev.ps1 -Test
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
echo.
pause
