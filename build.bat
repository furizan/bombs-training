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

set RELEASE=dist\Bombs-Training-windows
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller --noconfirm --clean bombs-training.spec
if errorlevel 1 exit /b 1

mkdir "%RELEASE%"
move /y dist\Bombs-Training.exe "%RELEASE%\"
copy /y config.json "%RELEASE%\"
copy /y display_defaults.json "%RELEASE%\"
copy /y map.png "%RELEASE%\"
copy /y USER-README.md "%RELEASE%\README.md"
xcopy /e /i /y pack "%RELEASE%\pack"

powershell -NoProfile -Command "Compress-Archive -Path 'dist/Bombs-Training-windows' -DestinationPath 'dist/Bombs-Training-windows.zip' -Force"
if errorlevel 1 exit /b 1

echo Built %RELEASE% and dist\Bombs-Training-windows.zip
