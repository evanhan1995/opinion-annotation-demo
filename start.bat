@echo off
cd /d "%~dp0"

set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python314"
set "PATH=%PYTHON%;%PYTHON%\Scripts;%PATH%"

echo ========================================
echo   Public Opinion Annotation System
echo ========================================
echo.
echo   Starting...
echo   Browser will open http://localhost:8501
echo   Close this window to stop the service
echo.
echo ========================================

start http://localhost:8501
python -m streamlit run app.py --server.port 8501 --server.headless true

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Startup failed.
    echo Checking Python installation at: %PYTHON%
    if not exist "%PYTHON%\python.exe" (
        echo Python not found! Please install Python 3.14 at:
        echo   %LOCALAPPDATA%\Programs\Python\Python314
    ) else (
        echo Python found. Try: pip install -r requirements.txt
    )
    pause
)
