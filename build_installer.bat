@echo off
setlocal EnableExtensions
title MLD Tools - Build Installer

cd /d "%~dp0"
echo ============================================================
echo  MLD TOOLS - BUILD DO INSTALADOR
echo ============================================================

for %%F in (MLDTools.exe MLDToolsSync.exe MLDToolsRetro.exe MLDToolsMedia.exe MLDToolsAlbum.exe) do (
    if not exist "build_exe\dist\%%F" (
        echo [ERRO] %%F nao encontrado. Execute build_exe.bat primeiro.
        pause
        exit /b 1
    )
)

if not exist "engine\tdl.exe" (
    echo [ERRO] engine\tdl.exe nao encontrado.
    pause
    exit /b 1
)

set "ISCC="
for %%I in (ISCC.exe) do if not "%%~$PATH:I"=="" set "ISCC=%%~$PATH:I"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo [ERRO] Inno Setup nao encontrado.
    echo Site oficial: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

if not exist "release\installer" mkdir "release\installer"
if exist "Icon.ico" (
    "%ISCC%" /DCustomIcon="Icon.ico" "MLDTools.iss"
) else (
    "%ISCC%" "MLDTools.iss"
)
if errorlevel 1 goto :erro

echo Instalador: release\installer\MLDTools_Setup_v3.0.0.exe
pause
exit /b 0

:erro
echo [ERRO] Falha durante a compilacao do instalador.
pause
exit /b 1
