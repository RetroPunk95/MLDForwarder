@echo off
setlocal EnableExtensions
title MLDForwarder - Build Release

cd /d "%~dp0"

echo ============================================================
echo  MLDFORWARDER - BUILD COMPLETO
echo ============================================================
echo.

call build_exe.bat
if errorlevel 1 (
    echo.
    echo [ERRO] Falha no build dos executaveis.
    exit /b 1
)

call build_installer.bat
if errorlevel 1 (
    echo.
    echo [ERRO] Falha no build do instalador.
    exit /b 1
)

echo.
echo ============================================================
echo  RELEASE COMPLETO GERADO
echo ============================================================
echo.
echo Portatil:
echo   release\MLDForwarder_Portable.zip
echo.
echo Instalador:
echo   release\installer\MLDForwarder_Setup_v2.8.0.exe
echo.
pause
