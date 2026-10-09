@echo off
REM ============================================================
REM  Make JARVIS start automatically when you log into Windows.
REM  Run this AFTER build.bat (needs dist\JARVIS.exe to exist).
REM ============================================================
cd /d "%~dp0"

if not exist "dist\JARVIS.exe" (
  echo dist\JARVIS.exe not found. Run build.bat first!
  pause
  exit /b 1
)

powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:APPDATA+'\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.lnk'); $s.TargetPath='%~dp0dist\JARVIS.exe'; $s.WorkingDirectory='%~dp0dist'; $s.Save()"

echo.
echo JARVIS will now start with Windows. Remove the shortcut from
echo   shell:startup  if you ever want to undo it.
pause
