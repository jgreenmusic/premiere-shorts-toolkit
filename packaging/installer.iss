; Inno Setup script for the Windows installer.   Build: packaging\build-windows.cmd
; Per-user install (no admin prompt). Uninstalling removes the app only - your projects,
; their <project>_captions / _shorts folders and settings are never touched.

#define AppName "Shorts Toolkit"
#define AppVersion "0.14.0"

[Setup]
AppId={{6E7A1C52-3B8D-4F1E-9C2A-5D4B8E0F7A31}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Julian Green
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=ShortsToolkit-Setup-{#AppVersion}
SetupIconFile=..\ui\icon.ico
UninstallDisplayIcon={app}\Shorts Toolkit.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\Shorts Toolkit\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Shorts Toolkit.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\Shorts Toolkit.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Shorts Toolkit.exe"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent
