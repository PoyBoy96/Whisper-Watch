#define AppName "Whisper Watch"
#define AppVersion "1.0.0"
#define AppPublisher "Whisper Watch"
#define AppExeName "WhisperWatch.exe"

[Setup]
AppId={{2E40A1C8-4E7D-4712-BD85-2A86A183985C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Whisper Watch
DefaultGroupName=Whisper Watch
SetupIconFile=..\assets\whisperwatch-icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=..\dist-installer
OutputBaseFilename=WhisperWatchInstaller_v1_0_0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableDirPage=no
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\WhisperWatch\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Whisper Watch"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Whisper Watch"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Whisper Watch"; Flags: nowait postinstall skipifsilent
