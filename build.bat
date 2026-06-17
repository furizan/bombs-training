@echo off
setlocal
cd /d "%~dp0"

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

if exist build rmdir /s /q build
if exist dist\release rmdir /s /q dist\release
if exist dist\Bombs-Crashmap.exe del /q dist\Bombs-Crashmap.exe

pyinstaller --noconfirm --clean bombs-crashmap.spec
if errorlevel 1 exit /b 1

set RELEASE=dist\release\Bombs-Crashmap-windows
mkdir "%RELEASE%"
copy /y dist\Bombs-Crashmap.exe "%RELEASE%\"
copy /y config.json "%RELEASE%\"
copy /y map.png "%RELEASE%\"
xcopy /e /i /y pack "%RELEASE%\pack"

powershell -NoProfile -Command "Compress-Archive -Path 'dist/release/Bombs-Crashmap-windows' -DestinationPath 'dist/Bombs-Crashmap-windows.zip' -Force"
if errorlevel 1 exit /b 1

echo Built dist\Bombs-Crashmap-windows.zip
