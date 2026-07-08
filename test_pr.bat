@echo off
chcp 65001 >nul 2>&1
title NoirGuard - Test PR

if "%GITHUB_TOKEN%"=="" (
    echo [!] GITHUB_TOKEN not set. Run setup.bat first.
    exit /b 1
)
if "%QWEN_API_KEY%"=="" (
    echo [!] QWEN_API_KEY not set. Run setup.bat first.
    exit /b 1
)

set REPO=RuslanSemchenko/NoirGuard
set BRANCH=test-vulnerable-%RANDOM%
set FILE=tests\vulnerable_app.py
set PYTHON=%~dp0.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo.
echo [1/5] Creating vulnerable test file...
> "%FILE%" (
    echo import os
    echo import sqlite3
    echo import subprocess
    echo.
    echo def get_user_data(user_id^):
    echo     conn = sqlite3.connect("users.db"^)
    echo     cursor = conn.cursor(^)
    echo     query = "SELECT * FROM users WHERE id = " + str(user_id^)
    echo     cursor.execute(query^)
    echo     return cursor.fetchall(^)
    echo.
    echo def execute_command(user_input^):
    echo     os.system(f"ping -c 4 {user_input}"^)
    echo.
    echo def load_module(module_name^):
    echo     exec(f"import {module_name}; {module_name}.run()"^)
)
echo [OK] %FILE% created

echo [2/5] Creating branch %BRANCH%...
git checkout -b %BRANCH% >nul 2>&1
git add "%FILE%" >nul 2>&1
git commit -m "test: vulnerable code for NoirGuard demo" >nul 2>&1
echo [OK] Branch created

echo [3/5] Pushing to origin/%BRANCH%...
git push origin %BRANCH% >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Push failed. Check your git remote.
    exit /b 1
)
echo [OK] Pushed

echo [4/5] Creating PR via GitHub API...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$body = @{title='Test: vulnerable code for NoirGuard'; head='%BRANCH%'; base='main'; body='Auto-generated PR with vulnerabilities for NoirGuard audit.'};" ^
    "$json = $body | ConvertTo-Json;" ^
    "$resp = Invoke-RestMethod -Uri 'https://api.github.com/repos/%REPO%/pulls' -Method Post -Headers @{Authorization=('token ' + '%GITHUB_TOKEN%'); Accept='application/vnd.github.v3+json'} -Body $json -ContentType 'application/json';" ^
    "Write-Output $resp.number" > "%TEMP%\pr_num.txt"
set /p PR_NUMBER=<"%TEMP%\pr_num.txt"
if "%PR_NUMBER%"=="" (
    echo [!] Failed to create PR
    type "%TEMP%\pr_num.txt"
    pause
    exit /b 1
)
echo [OK] PR #%PR_NUMBER% created: https://github.com/%REPO%/pull/%PR_NUMBER%

echo [5/5] Running NoirGuard PR audit...
"%PYTHON%" pr_audit.py %REPO% %PR_NUMBER%

echo.
echo ========================================
echo  Done! Check the PR for the audit result
echo  https://github.com/%REPO%/pull/%PR_NUMBER%
echo ========================================
echo.
pause
