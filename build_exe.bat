@echo off
setlocal EnableExtensions
title MLD Tools - Build EXE

cd /d "%~dp0"

echo ============================================================
echo  MLD TOOLS - BUILD PARA WINDOWS
echo ============================================================
echo.

set "PYTHON=py -3.12"
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python 3.12 nao foi encontrado.
    pause
    exit /b 1
)

if not exist "engine\tdl.exe" (
    echo [ERRO] engine\tdl.exe nao foi encontrado.
    pause
    exit /b 1
)

if not exist "Icon.ico" (
    echo [ERRO] Icon.ico nao foi encontrado.
    pause
    exit /b 1
)

if not exist "assets\app_icon_64.png" (
    echo [ERRO] assets\app_icon_64.png nao foi encontrado.
    pause
    exit /b 1
)

echo [1/8] Instalando dependencias...
%PYTHON% -m pip install -r requirements-build.txt
if errorlevel 1 goto :erro

echo [2/8] Limpando builds anteriores...
if exist "build_exe" rmdir /s /q "build_exe"
if exist "release" rmdir /s /q "release"
mkdir "build_exe"
mkdir "build_exe\dist"
mkdir "build_exe\spec"
mkdir "release"
mkdir "release\MLDTools_Portable"

copy /y "Icon.ico" "build_exe\spec\Icon.ico" >nul
xcopy /e /i /y "assets" "build_exe\spec\assets" >nul
if errorlevel 1 goto :erro
set "ICON_ARG=--icon=Icon.ico"
set "UI_DATA_ARGS=--add-data Icon.ico;. --add-data assets;assets"

echo [3/8] Compilando MLDTools.exe...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "MLDTools" --distpath "build_exe\dist" ^
    --workpath "build_exe\work_gui" --specpath "build_exe\spec" ^
    --collect-all "customtkinter" ^
    %ICON_ARG% %UI_DATA_ARGS% "gui.py"
if errorlevel 1 goto :erro

echo [4/8] Compilando motores de sincronizacao...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --console ^
    --name "MLDToolsSync" --distpath "build_exe\dist" ^
    --workpath "build_exe\work_sync" --specpath "build_exe\spec" ^
    --hidden-import "cryptg" ^
    "sincronizar.py"
if errorlevel 1 goto :erro

%PYTHON% -m PyInstaller --noconfirm --clean --onefile --console ^
    --name "MLDToolsRetro" --distpath "build_exe\dist" ^
    --workpath "build_exe\work_retro" --specpath "build_exe\spec" ^
    --hidden-import "cryptg" ^
    "sincronizar_antigas.py"
if errorlevel 1 goto :erro

echo [5/8] Compilando Central de midia...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "MLDToolsMedia" --distpath "build_exe\dist" ^
    --workpath "build_exe\work_media" --specpath "build_exe\spec" ^
    --collect-all "customtkinter" ^
    %ICON_ARG% %UI_DATA_ARGS% "media_app.py"
if errorlevel 1 goto :erro

echo [6/8] Compilando uploader de albuns...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --console ^
    --name "MLDToolsAlbum" --distpath "build_exe\dist" ^
    --workpath "build_exe\work_album" --specpath "build_exe\spec" ^
    --hidden-import "cryptg" ^
    "album_uploader.py"
if errorlevel 1 goto :erro

echo [7/8] Montando pacote portatil...
for %%F in (MLDTools.exe MLDToolsSync.exe MLDToolsRetro.exe MLDToolsMedia.exe MLDToolsAlbum.exe) do copy /y "build_exe\dist\%%F" "release\MLDTools_Portable\" >nul
mkdir "release\MLDTools_Portable\engine"
copy /y "engine\tdl.exe" "release\MLDTools_Portable\engine\" >nul
copy /y "engine\LICENSE-tdl.txt" "release\MLDTools_Portable\engine\" >nul
copy /y "engine\README-tdl.md" "release\MLDTools_Portable\engine\" >nul
copy /y "channels.default.json" "release\MLDTools_Portable\channels.json" >nul
copy /y "normal_config.default.json" "release\MLDTools_Portable\normal_config.json" >nul
copy /y "retro_config.default.json" "release\MLDTools_Portable\retro_config.json" >nul
copy /y "app_config.default.json" "release\MLDTools_Portable\app_config.json" >nul
for %%F in (.env.example README_PORTABLE.txt CHANGELOG.txt LICENSE THIRD_PARTY_NOTICES.md) do copy /y "%%F" "release\MLDTools_Portable\" >nul

echo [8/8] Compactando...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\MLDTools_Portable\*' -DestinationPath 'release\MLDTools_Portable.zip' -Force"
if errorlevel 1 goto :erro

echo.
echo EXE: release\MLDTools_Portable\MLDTools.exe
echo ZIP: release\MLDTools_Portable.zip
echo O pacote nao inclui .env, sessoes, rotas ou historico pessoal.
pause
exit /b 0

:erro
echo [ERRO] Falha durante o build.
pause
exit /b 1
