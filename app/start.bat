@echo off
cd /d "%~dp0"
venv\Scripts\python.exe app.py
echo.
echo App exited. If that was unexpected, whatever error appeared above is why.
pause
