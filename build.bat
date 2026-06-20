@echo off
setlocal
cd /d "%~dp0"

if not defined VIRTUAL_ENV (
  if not exist .venv\Scripts\python.exe (
    python -m venv .venv
  )
  call .venv\Scripts\activate.bat
)

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

python scripts\write_version.py
if errorlevel 1 exit /b 1

set STAGING=build\bombs-training-windows

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller --noconfirm --clean bombs-training.spec
if errorlevel 1 exit /b 1

mkdir "%STAGING%"
move /y dist\bombs-training.exe "%STAGING%\"
xcopy /e /i /y assets "%STAGING%\assets"
copy /y docs\user-readme.md "%STAGING%\README.md"

mkdir dist
powershell -NoProfile -Command "Compress-Archive -Path 'build/bombs-training-windows' -DestinationPath 'dist/bombs-training-windows.zip' -Force"
if errorlevel 1 exit /b 1

rmdir /s /q "%STAGING%"
if exist dist\bombs-training-windows rmdir /s /q dist\bombs-training-windows
if exist dist\bombs-training.exe del /q dist\bombs-training.exe

echo Built dist\bombs-training-windows.zip
