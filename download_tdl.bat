@echo off
setlocal EnableExtensions
title MLD Tools - Atualizar motor tdl

cd /d "%~dp0"
set "TDL_VERSION=v0.20.4"
set "TDL_SHA256=3f219779c07a4be628c34491b9910c18a3b0a0ca0b0aa4f283bb83ab33b007c8"
set "TDL_ZIP=%TEMP%\tdl_Windows_64bit_%TDL_VERSION%.zip"

echo Baixando tdl %TDL_VERSION% do repositorio oficial...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/iyear/tdl/releases/download/%TDL_VERSION%/tdl_Windows_64bit.zip' -OutFile '%TDL_ZIP%'"
if errorlevel 1 goto :erro

for /f "tokens=*" %%H in ('powershell -NoProfile -Command "(Get-FileHash '%TDL_ZIP%' -Algorithm SHA256).Hash.ToLower()"') do set "ACTUAL_SHA256=%%H"
if /i not "%ACTUAL_SHA256%"=="%TDL_SHA256%" (
    echo [ERRO] O checksum do arquivo baixado nao corresponde ao publicado.
    goto :erro
)

if not exist "engine" mkdir "engine"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -Path '%TDL_ZIP%' -DestinationPath '%TEMP%\mldtools_tdl' -Force; Copy-Item '%TEMP%\mldtools_tdl\tdl.exe' 'engine\tdl.exe' -Force; Copy-Item '%TEMP%\mldtools_tdl\LICENSE' 'engine\LICENSE-tdl.txt' -Force; Copy-Item '%TEMP%\mldtools_tdl\README.md' 'engine\README-tdl.md' -Force"
if errorlevel 1 goto :erro

echo Motor atualizado e verificado.
pause
exit /b 0

:erro
echo Nao foi possivel atualizar o motor tdl.
pause
exit /b 1
