@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python and enable Add Python to PATH.
    pause
    exit /b 1
)
python -u "%~dp0upload_to_github.py" %*
set "UPLOAD_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %UPLOAD_EXIT%
