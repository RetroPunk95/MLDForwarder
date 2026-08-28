@echo off
setlocal EnableExtensions
title MLD Tools - Build Release
cd /d "%~dp0"

call build_exe.bat
if errorlevel 1 exit /b 1
call build_installer.bat
if errorlevel 1 exit /b 1

echo Portatil: release\MLDTools_Portable.zip
echo Instalador: release\installer\MLDTools_Setup_v3.0.0.exe
pause
