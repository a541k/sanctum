@echo off
rem Windows: double-click this file to start My Journal.
rem The first run makes a private Python environment in .venv and downloads what the app needs.
setlocal
cd /d "%~dp0"
set "VENV=.venv"

rem 1. A private Python environment, made once
if exist "%VENV%\Scripts\python.exe" goto :install
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "PY=py -3"
if not defined PY (python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "PY=python")
if not defined PY goto :no_python
echo Setting up My Journal for the first time. This takes a few minutes...
%PY% -m venv "%VENV%"
if errorlevel 1 (
    rmdir /s /q "%VENV%" 2>nul
    goto :failed
)

rem 2. What the app needs, installed again only when requirements.txt changes
:install
fc /b requirements.txt "%VENV%\requirements.installed" >nul 2>&1 && goto :start
echo Downloading what My Journal needs (about 300 MB). This takes a few minutes...
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :failed
copy /y requirements.txt "%VENV%\requirements.installed" >nul

rem 3. Start the app without a console window
:start
start "" "%VENV%\Scripts\pythonw.exe" -m journal_app
exit /b 0

:no_python
echo.
echo My Journal needs Python 3.9 or newer, and it isn't installed.
echo Get it from https://www.python.org/downloads/
echo When installing, tick "Add python.exe to PATH". Then double-click run.bat again.
echo.
pause
exit /b 1

:failed
echo.
echo Setup didn't finish. Check your internet connection and double-click run.bat to try again.
echo If it keeps failing, delete the .venv folder and try again.
echo.
pause
exit /b 1
