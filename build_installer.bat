@echo off
setlocal EnableExtensions
title MLDForwarder - Build Installer

cd /d "%~dp0"

echo ============================================================
echo  MLDFORWARDER - BUILD DO INSTALADOR
echo ============================================================
echo.

if not exist "build_exe\dist\MLDForwarder.exe" (
    echo [ERRO] MLDForwarder.exe nao encontrado.
    echo Execute build_exe.bat primeiro.
    echo.
    pause
    exit /b 1
)

if not exist "build_exe\dist\MLDForwarderSync.exe" (
    echo [ERRO] MLDForwarderSync.exe nao encontrado.
    echo Execute build_exe.bat primeiro.
    echo.
    pause
    exit /b 1
)

if not exist "build_exe\dist\MLDForwarderRetro.exe" (
    echo [ERRO] MLDForwarderRetro.exe nao encontrado.
    echo Execute build_exe.bat primeiro.
    echo.
    pause
    exit /b 1
)

set "ISCC="

for %%I in (ISCC.exe) do (
    if not "%%~$PATH:I"=="" set "ISCC=%%~$PATH:I"
)

if not defined ISCC if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 7\ISCC.exe"

if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo [ERRO] O compilador do Inno Setup nao foi encontrado.
    echo.
    echo Instale o Inno Setup e execute este arquivo novamente.
    echo Site oficial: https://jrsoftware.org/isdl.php
    echo.
    pause
    exit /b 1
)

if not exist "release\installer" mkdir "release\installer"

echo Compilador encontrado:
echo   %ISCC%
echo.

if exist "icon.ico" (
    echo Icone personalizado encontrado.
    "%ISCC%" /DCustomIcon="icon.ico" "MLDForwarder.iss"
) else (
    echo Nenhum icon.ico encontrado. Usando o icone padrao do executavel.
    "%ISCC%" "MLDForwarder.iss"
)

if errorlevel 1 goto :erro

echo.
echo ============================================================
echo  INSTALADOR CONCLUIDO
echo ============================================================
echo.
echo Arquivo:
echo   release\installer\MLDForwarder_Setup_v2.8.0.exe
echo.
pause
exit /b 0

:erro
echo.
echo ============================================================
echo  ERRO DURANTE A COMPILACAO DO INSTALADOR
echo ============================================================
echo.
pause
exit /b 1
