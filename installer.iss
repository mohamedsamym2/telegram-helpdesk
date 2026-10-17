; Inno Setup 7 Script for IT Support Helpdesk
; Compiles standalone installer without requiring Python on target system

#define MyAppName "IT Support Helpdesk"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "IT Department"
#define MyAppURL "http://localhost:8080"
#define MyAppExeName "ITSupportHelpdesk.exe"

[Setup]
AppId={{8B2C4F31-9A76-4F3D-94D1-016E85C2FA71}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=ITSupportHelpdesk_Setup_v2.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Dirs]
Name: "{app}"; Permissions: users-full
Name: "{app}\static"; Permissions: users-full
Name: "{app}\static\uploads"; Permissions: users-full

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Automatically start server on Windows boot (Silent background)"; GroupDescription: "System Integration:"; Flags: checkedonce

[Files]
; Standalone compiled files
Source: "dist\ITSupportHelpdesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Static Web UI assets
Source: "static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs
; Background starter and stopper scripts
Source: "start_server.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "stop_server.bat"; DestDir: "{app}"; Flags: ignoreversion
; Template database (never overwritten on reinstall, never deleted on uninstall to protect tickets)
Source: "helpdesk.db"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\{#MyAppName} Dashboard"; Filename: "http://localhost:8080"
Name: "{group}\Start Server (Background)"; Filename: "wscript.exe"; Parameters: """{app}\start_server.vbs"""; WorkingDir: "{app}"
Name: "{group}\Stop Server"; Filename: "{app}\stop_server.bat"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName} Dashboard"; Filename: "http://localhost:8080"; Tasks: desktopicon
Name: "{autodesktop}\Start Server (Background)"; Filename: "wscript.exe"; Parameters: """{app}\start_server.vbs"""; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{commonstartup}\{#MyAppName}"; Filename: "wscript.exe"; Parameters: """{app}\start_server.vbs"""; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "wscript.exe"; Parameters: """{app}\start_server.vbs"""; Description: "Start {#MyAppName} Server now in background"; Flags: nowait postinstall skipifsilent
Filename: "http://localhost:8080"; Description: "Open Web Dashboard in browser"; Flags: shellexec nowait postinstall skipifsilent

[Code]
// Terminate server process gracefully before installation or uninstallation
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM ITSupportHelpdesk.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM ITSupportHelpdesk.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
