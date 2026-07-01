; Inno Setup Script for TE71/TE73 Meter Tool
; Defines the installation wizard, shortcuts, and uninstaller.

#define MyAppName "Meter Tool"
#define MyAppVersion "1.0"
#define MyAppPublisher "Toshelectroapparat"
#define MyAppExeName "MeterTool.exe"

[Setup]
; AppId uniquely identifies this application for the uninstaller
AppId={{9F8E4D51-40EA-41FE-8F2D-39F22E58BE3C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; PrivilegesRequired=lowest means it installs per-user by default (no admin required unless installing for all users)
PrivilegesRequired=lowest
OutputDir=C:\bakhromdev\meter_tool\dist
OutputBaseFilename=MeterToolSetup
SetupIconFile=C:\bakhromdev\meter_tool\app_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "C:\bakhromdev\meter_tool\dist\MeterTool.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
