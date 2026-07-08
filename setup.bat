@echo off
chcp 65001 >nul 2>&1
title NoirGuard Setup
cd /d "%~dp0"

:: ===============================================================
:: 1. Find Python
:: ===============================================================
set PYTHON=
where python 2>nul >nul
if %errorlevel% equ 0 set PYTHON=python
if "%PYTHON%"=="" (
    for /d %%i in ("C:\Python*" "%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%i\python.exe" set PYTHON=%%i\python.exe
    )
)
if "%PYTHON%"=="" (
    echo [ERROR] Python not found. Install Python 3.14+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python: %PYTHON%

:: ===============================================================
:: 2. Create venv if needed
:: ===============================================================
if not exist ".venv\Scripts\python.exe" (
    echo [..] Creating virtual environment...
    "%PYTHON%" -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)
set VENV_PY=%~dp0.venv\Scripts\python.exe

:: ===============================================================
:: 3. Install dependencies
:: ===============================================================
echo [..] Installing dependencies...
"%VENV_PY%" -m pip install -r requirements.txt pylint >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed. Check internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: ===============================================================
:: 4. Set environment variables
::    TIP: Create a copy named 'setup_private.bat' with your keys
::         setup_private.bat is already in .gitignore
:: ===============================================================
:set_keys
cls
echo ========================================
echo   NoirGuard - Environment Setup
echo ========================================
echo.
echo   No API keys detected.
echo   You need to set the following:
echo.
echo   [1] QWEN_API_KEY - https://dashscope.aliyun.com
echo       Model: qwen-max
echo.
echo   [2] QWEN_BASE_URL (if custom endpoint)
echo       Default: https://dashscope.aliyuncs.com/compatible-mode/v1
echo.
echo   [3] GITHUB_TOKEN - https://github.com/settings/tokens
echo       Permissions: repo, issues, pull requests
echo.
echo   [4] SNYK_TOKEN (optional) - https://app.snyk.io
echo       Install CLI: npm install -g snyk
echo.
echo ========================================
echo   Choose option:
echo ========================================
echo.
echo   [M] Manual - enter keys now
echo   [F] Use .env file (create .env with your keys)
echo   [S] Skip - set manually later
echo   [Q] Quit
echo.
set /p CHOICE="> "

if /i "%CHOICE%"=="M" goto manual_keys
if /i "%CHOICE%"=="F" goto dotenv_keys
if /i "%CHOICE%"=="S" goto menu
if /i "%CHOICE%"=="Q" exit /b 0
goto set_keys

:manual_keys
cls
echo Enter your API keys (input is hidden).
echo.
set /p QWEN_API_KEY="QWEN_API_KEY: "
if "%QWEN_API_KEY%"=="" set QWEN_API_KEY=not_set
set /p QWEN_BASE_URL="QWEN_BASE_URL (press Enter for default): "
if "%QWEN_BASE_URL%"=="" set QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
set /p GITHUB_TOKEN="GITHUB_TOKEN: "
if "%GITHUB_TOKEN%"=="" set GITHUB_TOKEN=not_set
goto menu

:dotenv_keys
if exist ".env" (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if "%%a"=="QWEN_API_KEY" set QWEN_API_KEY=%%b
        if "%%a"=="QWEN_BASE_URL" set QWEN_BASE_URL=%%b
        if "%%a"=="GITHUB_TOKEN" set GITHUB_TOKEN=%%b
        if "%%a"=="SNYK_TOKEN" set SNYK_TOKEN=%%b
    )
    echo [OK] Loaded from .env
    timeout /t 2 >nul
) else (
    echo [ERROR] .env file not found
    echo Create .env with content:
    echo   QWEN_API_KEY=your-key
    echo   QWEN_BASE_URL=https://...
    echo   GITHUB_TOKEN=your-token
    timeout /t 4 >nul
)
goto menu

:: ===============================================================
:: 5. Menu
:: ===============================================================
:menu
cls
echo ========================================
echo   NoirGuard - DevSecOps Auditor
echo ========================================
echo.
echo   Python:  %VENV_PY%
if not "%QWEN_API_KEY%"=="" echo   QA Key:  %QWEN_API_KEY:~0,15%...
if not "%GITHUB_TOKEN%"=="" echo   GH Token: %GITHUB_TOKEN:~0,15%...
if "%QWEN_API_KEY%"=="" echo   [Keys not set]
echo.
echo ========================================
echo   Select action:
echo ========================================
echo.
echo   [1] Quick test (run_audit.py)
echo   [2] Full PR test (create PR + audit + comment)
echo   [3] Start web server (localhost:8000)
echo   [4] Reset API keys
echo   [5] Exit
echo.
set /p CHOICE="> "

if "%CHOICE%"=="1" goto run_audit
if "%CHOICE%"=="2" goto test_pr
if "%CHOICE%"=="3" goto web_server
if "%CHOICE%"=="4" goto set_keys
if "%CHOICE%"=="5" exit /b 0
goto menu

:run_audit
cls
echo [..] Running audit on test code...
"%VENV_PY%" run_audit.py
echo.
pause
goto menu

:test_pr
cls
call test_pr.bat
goto menu

:web_server
cls
echo [..] Starting web server on http://127.0.0.1:8000
echo     Press Ctrl+C to stop
echo.
"%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
goto menu
