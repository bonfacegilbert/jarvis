@echo off
REM ============================================================
REM  Build JARVIS into a real Windows app (JARVIS.exe)
REM  Double-click this file. The exe lands in dist\JARVIS.exe
REM  NOTE: Ollama must still be installed + running for AI chat.
REM ============================================================
cd /d "%~dp0"

echo [1/3] Installing PyInstaller...
pip install pyinstaller || (echo FAILED to install PyInstaller & pause & exit /b 1)

echo [2/3] Building JARVIS.exe (this takes a few minutes)...
pyinstaller --onefile --windowed --name JARVIS --icon=jarvis.ico ^
  --hidden-import=pyttsx3.drivers.sapi5 ^
  jarvis_gui.py || (echo BUILD FAILED & pause & exit /b 1)

echo [3/3] Copying icon and config next to the exe...
copy /y jarvis.ico dist\ >nul
copy /y jarvis_config.json dist\ >nul

echo.
echo ============================================================
echo  DONE! Your app is at: dist\JARVIS.exe
echo  Double-click it to run. Say "hi" for your morning briefing.
echo ============================================================
pause
