#define MyAppName "MLDForwarder"
#define MyAppVersion "2.8.1"
#define MyAppExeName "MLDForwarder.exe"
#define MyAppSyncExeName "MLDForwarderSync.exe"
#define MyAppRetroExeName "MLDForwarderRetro.exe"

[Setup]
AppId={{C47D168A-3449-49CE-B52C-A7E10F252451}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\MLDForwarder
DefaultGroupName=MLDForwarder
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release\installer
OutputBaseFilename=MLDForwarder_Setup_v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible

#ifdef CustomIcon
SetupIconFile={#CustomIcon}
#endif

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "build_exe\dist\MLDForwarder.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "build_exe\dist\MLDForwarderSync.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "build_exe\dist\MLDForwarderRetro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "README_PORTABLE.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion
Source: "CHANGELOG.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MLDForwarder"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\MLDForwarder"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir MLDForwarder"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Arquivos temporários de controle podem ser removidos com segurança.
Type: files; Name: "{app}\sync_stop.flag"
Type: files; Name: "{app}\retro_stop.flag"

; Intencionalmente NÃO removemos:
; .env
; *.session
; channels.json
; sync_progress.json
; historico_progress.json
; normal_config.json
; retro_config.json
; app_config.json
; Assim os dados do usuário sobrevivem à desinstalação.
