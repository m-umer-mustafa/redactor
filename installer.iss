[Setup]
AppName=The Redactor
AppVersion=1.0.0
DefaultDirName={pf}\The Redactor
DefaultGroupName=The Redactor
OutputDir=dist
OutputBaseFilename=Redactor_Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\Redactor.exe
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Redactor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\The Redactor"; Filename: "{app}\Redactor.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,The Redactor}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\The Redactor"; Filename: "{app}\Redactor.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\Redactor.exe"; Description: "{cm:LaunchProgram,The Redactor}"; Flags: nowait postinstall skipifsilent
