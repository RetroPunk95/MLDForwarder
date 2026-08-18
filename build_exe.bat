@echo off
setlocal EnableExtensions
title MLDForwarder - Build EXE

cd /d "%~dp0"

echo ============================================================
echo  MLDFORWARDER - BUILD PARA WINDOWS
echo ============================================================
echo.

set "PYTHON=py -3.12"

%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python 3.12 nao foi encontrado.
    echo Instale o Python 3.12 e tente novamente.
    echo.
    pause
    exit /b 1
)

echo [1/6] Instalando dependencias de build...
%PYTHON% -m pip install -r requirements-build.txt
if errorlevel 1 goto :erro

echo.
echo [2/6] Limpando builds anteriores...
if exist "build_exe" rmdir /s /q "build_exe"
if exist "release" rmdir /s /q "release"

mkdir "build_exe"
mkdir "build_exe\dist"
mkdir "build_exe\spec"
mkdir "release"
mkdir "release\MLDForwarder_Portable"

set "ICON_ARG="
if exist "icon.ico" (
    echo Icone personalizado encontrado: icon.ico
    copy /y "icon.ico" "build_exe\spec\icon.ico" >nul
    set "ICON_ARG=--icon=icon.ico"
)

echo.
echo [3/6] Compilando MLDForwarder.exe...
%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "MLDForwarder" ^
    --distpath "build_exe\dist" ^
    --workpath "build_exe\work_gui" ^
    --specpath "build_exe\spec" ^
    %ICON_ARG% ^
    "gui.py"
if errorlevel 1 goto :erro

echo.
echo [4/6] Compilando MLDForwarderSync.exe...
%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --console ^
    --name "MLDForwarderSync" ^
    --distpath "build_exe\dist" ^
    --workpath "build_exe\work_sync" ^
    --specpath "build_exe\spec" ^
    "sincronizar.py"
if errorlevel 1 goto :erro

echo.
echo [5/6] Compilando MLDForwarderRetro.exe...
%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --console ^
    --name "MLDForwarderRetro" ^
    --distpath "build_exe\dist" ^
    --workpath "build_exe\work_retro" ^
    --specpath "build_exe\spec" ^
    "sincronizar_antigas.py"
if errorlevel 1 goto :erro

echo.
echo [6/6] Montando pacote portatil...

copy /y "build_exe\dist\MLDForwarder.exe" "release\MLDForwarder_Portable\" >nul
copy /y "build_exe\dist\MLDForwarderSync.exe" "release\MLDForwarder_Portable\" >nul
copy /y "build_exe\dist\MLDForwarderRetro.exe" "release\MLDForwarder_Portable\" >nul

copy /y "channels.default.json" "release\MLDForwarder_Portable\channels.json" >nul
copy /y "normal_config.default.json" "release\MLDForwarder_Portable\normal_config.json" >nul
copy /y "retro_config.default.json" "release\MLDForwarder_Portable\retro_config.json" >nul
copy /y "app_config.default.json" "release\MLDForwarder_Portable\app_config.json" >nul
copy /y ".env.example" "release\MLDForwarder_Portable\" >nul
copy /y "README_PORTABLE.txt" "release\MLDForwarder_Portable\" >nul
copy /y "CHANGELOG.txt" "release\MLDForwarder_Portable\" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Compress-Archive -Path 'release\MLDForwarder_Portable\*' -DestinationPath 'release\MLDForwarder_Portable.zip' -Force"

echo.
echo ============================================================
echo  BUILD CONCLUIDO
echo ============================================================
echo.
echo EXEs:
echo   release\MLDForwarder_Portable\MLDForwarder.exe
echo   release\MLDForwarder_Portable\MLDForwarderSync.exe
echo   release\MLDForwarder_Portable\MLDForwarderRetro.exe
echo.
echo ZIP:
echo   release\MLDForwarder_Portable.zip
echo.
echo IMPORTANTE:
echo Este pacote e LIMPO. Ele nao inclui seu .env, sessao,
echo rotas pessoais ou arquivos de progresso.
echo.
pause
exit /b 0

:erro
echo.
echo ============================================================
echo  ERRO DURANTE O BUILD
echo ============================================================
echo.
echo Revise as mensagens acima.
echo.
pause
exit /b 1
