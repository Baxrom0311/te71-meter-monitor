; Inno Setup Script for TE71/TE73 Meter Tool
; Defines the installation wizard, shortcuts, and uninstaller.
; Resolves dev path hardcoding and packages all binaries recursively.

#define MyAppName "Meter Tool"
#define MyAppVersion "2.0.0"
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
OutputDir=dist
OutputBaseFilename=MeterToolSetup
SetupIconFile=app_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; Enable clean upgrades by overwriting files during install
AlwaysOverwrite=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Source paths are relative to the location of this .iss file
Source: "dist\MeterTool\MeterTool.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\MeterTool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Clean up app settings from Windows Registry on uninstall (deletes HKEY_CURRENT_USER\Software\Toshelectroapparat\MeterTool)
Root: HKCU; Subkey: "Software\Toshelectroapparat\MeterTool"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Toshelectroapparat"; Flags: uninsdeletekeyifempty

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
