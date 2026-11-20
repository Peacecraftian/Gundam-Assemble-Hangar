@echo off
setlocal
echo Hangar Terminal sign-in setup for the current Windows user
choice /C ERQ /M "Enable automatic start, Remove the task, or Quit"
if errorlevel 3 exit /b 0
if errorlevel 2 goto remove
if not errorlevel 1 exit /b 0
set "action="
goto run
:remove
set "action=-Remove"
:run
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0StationStartup.ps1" %action%
set "result=%errorlevel%"
pause
exit /b %result%
