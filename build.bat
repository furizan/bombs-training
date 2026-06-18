@echo off
setlocal
cd /d "%~dp0"

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

if exist build rmdir /s /q build
if exist dist\release rmdir /s /q dist\release
if exist dist\Bombs-Training.exe del /q dist\Bombs-Training.exe

pyinstaller --noconfirm --clean bombs-training.spec
if errorlevel 1 exit /b 1

set RELEASE=dist\release\Bombs-Training-windows
mkdir "%RELEASE%"
copy /y dist\Bombs-Training.exe "%RELEASE%\"
copy /y config.json "%RELEASE%\"
copy /y map.png "%RELEASE%\"
xcopy /e /i /y pack "%RELEASE%\pack"

powershell -NoProfile -Command "Compress-Archive -Path 'dist/release/Bombs-Training-windows' -DestinationPath 'dist/Bombs-Training-windows.zip' -Force"
if errorlevel 1 exit /b 1

echo Built dist\Bombs-Training-windows.zip
