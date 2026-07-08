@echo off
chcp 65001 >nul 2>&1
title NoirGuard Cleanup
cd /d "%~dp0"

if "%GITHUB_TOKEN%"=="" (
    echo [ERROR] GITHUB_TOKEN not set. Run setup.bat first.
    pause
    exit /b 1
)

set REPO=RuslanSemchenko/NoirGuard
set API=https://api.github.com/repos/%REPO%

echo ========================================
echo   NoirGuard - Cleanup
echo ========================================
echo.

:: ===============================================================
:: 1. Close all open PRs
:: ===============================================================
echo [1/4] Closing open PRs...
powershell -NoProfile -Command ^
    "$token='%GITHUB_TOKEN%'; $api='%API%';" ^
    "$h=@{Authorization=('token '+$token); Accept='application/vnd.github.v3+json'};" ^
    "$prs=Invoke-RestMethod -Uri ($api+'/pulls?state=open') -Headers $h;" ^
    "if ($prs.Count -eq 0 -or $prs.Count -eq $null) { Write-Output '  No open PRs found.' } else {" ^
    "  foreach ($pr in $prs) {" ^
    "    Invoke-RestMethod -Uri ($api+'/pulls/'+$pr.number) -Method Patch -Headers $h -Body '{\"state\":\"closed\"}' -ContentType 'application/json' | Out-Null;" ^
    "    Write-Output ('  Closed PR #'+$pr.number+': '+$pr.title);" ^
    "  }" ^
    "}"
echo [OK]

:: ===============================================================
:: 2. Delete remote test branches
:: ===============================================================
echo [2/4] Deleting test branches from GitHub...
powershell -NoProfile -Command ^
    "$token='%GITHUB_TOKEN%'; $api='%API%';" ^
    "$h=@{Authorization=('token '+$token); Accept='application/vnd.github.v3+json'};" ^
    "$branches=Invoke-RestMethod -Uri ($api+'/branches') -Headers $h;" ^
    "$count=0;" ^
    "foreach ($b in $branches) {" ^
    "  if ($b.name -like 'test-vulnerable*') {" ^
    "    Invoke-RestMethod -Uri ($api+'/git/refs/heads/'+$b.name) -Method Delete -Headers $h | Out-Null;" ^
    "    Write-Output ('  Deleted: '+$b.name); $count++" ^
    "  }" ^
    "}" ^
    "if ($count -eq 0) { Write-Output '  No test branches found.' }"
echo [OK]

:: ===============================================================
:: 3. Delete local branches
:: ===============================================================
echo [3/4] Cleaning local test branches...
for /f "delims=" %%b in ('git branch --list "test-vulnerable*"') do (
    git branch -D "%%b" 2>nul
    if not errorlevel 1 echo   Deleted local: %%b
)
echo [OK]

:: ===============================================================
:: 4. Delete local test file
:: ===============================================================
echo [4/4] Removing test file...
if exist "tests\vulnerable_app.py" (
    del "tests\vulnerable_app.py" && echo   Removed tests\vulnerable_app.py
) else (
    echo   No test file found
)

:: ===============================================================
echo.
echo ========================================
echo  Cleanup complete. Switch to main:
echo    git checkout main
echo ========================================
echo.
pause
