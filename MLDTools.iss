#define MyAppName "MLD Tools"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Mídia Local Downloads"
#define MyAppExeName "MLDTools.exe"

[Setup]
; Mantém o AppId do MLDForwarder para que a v3 seja reconhecida como atualização.
AppId={{C47D168A-3449-49CE-B52C-A7E10F252451}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\MLDTools
DefaultGroupName={#MyAppName}
; O diretório anterior é reutilizado, mas o grupo de atalhos recebe a nova marca.
UsePreviousGroup=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release\installer
OutputBaseFilename=MLDTools_Setup_v{#MyAppVersion}
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

[InstallDelete]
; Limpeza exata da v2.x. Dados do usuário e outros arquivos não são tocados.
Type: files; Name: "{app}\MLDForwarder.exe"
Type: files; Name: "{app}\MLDForwarderSync.exe"
Type: files; Name: "{app}\MLDForwarderRetro.exe"
Type: files; Name: "{userdesktop}\MLDForwarder.lnk"
Type: files; Name: "{userprograms}\MLDForwarder\MLDForwarder.lnk"
Type: dirifempty; Name: "{userprograms}\MLDForwarder"

[Files]
Source: "build_exe\dist\MLDTools.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "build_exe\dist\MLDToolsSync.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "build_exe\dist\MLDToolsRetro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "build_exe\dist\MLDToolsMedia.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "build_exe\dist\MLDToolsAlbum.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "engine\tdl.exe"; DestDir: "{app}\engine"; Flags: ignoreversion
Source: "engine\LICENSE-tdl.txt"; DestDir: "{app}\engine"; Flags: ignoreversion
Source: "engine\README-tdl.md"; DestDir: "{app}\engine"; Flags: ignoreversion
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "README_PORTABLE.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion
Source: "CHANGELOG.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MLD Tools"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\MLD Tools"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir MLD Tools"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\sync_stop.flag"
Type: files; Name: "{app}\retro_stop.flag"
Type: filesandordirs; Name: "{app}\temp_transferencias"

; Credenciais, sessões, rotas, progresso, configurações e histórico
; permanecem na pasta para sobreviver a reinstalações e atualizações.
