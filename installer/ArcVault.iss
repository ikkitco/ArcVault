; ArcVault installer (installer plan, step 4). Built by build.bat with Inno Setup 6:
;     ISCC.exe /DAppVersion=0.5.1 installer\ArcVault.iss
; Packs dist\ArcVault into dist\ArcVault-Setup-<version>.exe.
;
; Decisions (ROADMAP "Installer plan"):
;  * Per-user install, no admin prompt: %LOCALAPPDATA%\Programs\ArcVault by default.
;    Players can choose another folder; a red note under the box says another folder may
;    need the installer run as administrator, and Setup checks it can write there.
;  * Your files live in Documents\ArcVault and are NEVER removed by the uninstaller.
;    Working files (%LOCALAPPDATA%\ArcVault: cache, window, logs, settings) are removed.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8C4E2B71-5A3D-4F6E-9B12-7D0A6C3E41F9}
AppName=ArcVault
AppVersion={#AppVersion}
AppVerName=ArcVault {#AppVersion}
AppPublisher=iKkitco
AppPublisherURL=https://ikkit.co
AppComments=From collection to strategy: MTG Arena collection intelligence for your PC.
DefaultDirName={userpf}\ArcVault
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UsedUserAreasWarning=no
DisableDirPage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile=..\brand\arcvault.ico
UninstallDisplayIcon={app}\ArcVault.exe
UninstallDisplayName=ArcVault
InfoBeforeFile=before_install.txt
OutputDir=..\dist
OutputBaseFilename=ArcVault-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
VersionInfoVersion={#AppVersion}
VersionInfoCompany=iKkitco
VersionInfoDescription=ArcVault Setup
VersionInfoProductName=ArcVault
CloseApplications=no
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\ArcVault\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Microsoft's small WebView2 installer (downloaded by build.bat). Only used if the PC lacks WebView2.
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
Name: "{autoprograms}\ArcVault"; Filename: "{app}\ArcVault.exe"; Comment: "ArcVault - collection intelligence for MTG Arena"
Name: "{autodesktop}\ArcVault"; Filename: "{app}\ArcVault.exe"; Comment: "ArcVault - collection intelligence for MTG Arena"; Tasks: desktopicon

[Run]
; ArcVault's window is drawn by the Microsoft Edge WebView2 Runtime. Windows 11 and updated Windows 10
; have it; clean or older PCs (and Windows Sandbox) don't, which leaves an empty window.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime (needed to show ArcVault's window)..."; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\ArcVault.exe"; Description: "Start ArcVault now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; working files only - Documents\ArcVault (your collection and history) is never touched
Type: filesandordirs; Name: "{localappdata}\ArcVault"
Type: files; Name: "{userstartup}\ArcVault.lnk"
Type: filesandordirs; Name: "{app}"

[Code]
var
  DirWarn: TNewStaticText;

{ Microsoft's documented check: the WebView2 Runtime's "pv" version value, per machine or per user }
function WebView2Version(RootKey: Integer; SubKey: String): String;
begin
  if not RegQueryStringValue(RootKey, SubKey, 'pv', Result) then
    Result := '';
end;

function NeedsWebView2: Boolean;
var
  V: String;
begin
  V := WebView2Version(HKLM32, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}');
  if (V = '') or (V = '0.0.0.0') then
    V := WebView2Version(HKLM64, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}');
  if (V = '') or (V = '0.0.0.0') then
    V := WebView2Version(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}');
  Result := (V = '') or (V = '0.0.0.0');
end;

function DefaultDir: String;
begin
  Result := ExpandConstant('{userpf}\ArcVault');
end;

{ red note under the folder box when the folder isn't the recommended one }
procedure UpdateDirWarning;
begin
  DirWarn.Visible := CompareText(RemoveBackslashUnlessRoot(Trim(WizardForm.DirEdit.Text)),
                                 RemoveBackslashUnlessRoot(DefaultDir)) <> 0;
end;

procedure DirEditChange(Sender: TObject);
begin
  UpdateDirWarning;
end;

procedure InitializeWizard;
begin
  DirWarn := TNewStaticText.Create(WizardForm);
  DirWarn.Parent := WizardForm.SelectDirPage;
  DirWarn.Left := WizardForm.DirEdit.Left;
  DirWarn.Top := WizardForm.DirEdit.Top + WizardForm.DirEdit.Height + ScaleY(10);
  DirWarn.AutoSize := False;
  DirWarn.WordWrap := True;
  DirWarn.Width := WizardForm.DirBrowseButton.Left + WizardForm.DirBrowseButton.Width - DirWarn.Left;
  DirWarn.Height := ScaleY(48);
  DirWarn.Font.Color := clRed;
  DirWarn.Caption :=
    'This isn''t the recommended folder (' + DefaultDir + '). ' +
    'Installing to another folder may require running the installer as administrator ' +
    '(right-click it and choose "Run as administrator").';
  DirWarn.Visible := False;
  WizardForm.DirEdit.OnChange := @DirEditChange;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectDir then
    UpdateDirWarning;
end;

{ can Setup actually write to the chosen folder? (no admin rights -> Program Files etc. fail) }
function CanWriteTo(Dir: String): Boolean;
var
  Probe: String;
  Existed: Boolean;
begin
  Existed := DirExists(Dir);
  if Existed then
    Result := True
  else
    Result := ForceDirectories(Dir);
  if Result then
  begin
    Probe := AddBackslash(Dir) + 'arcvault_write_test.tmp';
    Result := SaveStringToFile(Probe, 'ok', False);
    if Result then
      DeleteFile(Probe);
  end;
  if (not Existed) and DirExists(Dir) then
    RemoveDir(Dir);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpSelectDir) and not CanWriteTo(WizardDirValue) then
  begin
    MsgBox('Setup can''t write to this folder without administrator rights:' + #13#10 +
           WizardDirValue + #13#10#13#10 +
           'Choose another folder, or close Setup and run it as administrator ' +
           '(right-click it and choose "Run as administrator").', mbError, MB_OK);
    Result := False;
  end;
end;

{ Windows won't replace a running exe: close ArcVault (window, tray, auto-export) and its reader }
procedure CloseArcVault;
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /t /im ArcVault.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im mtga-tracker-daemon.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CloseArcVault;
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  CloseArcVault;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    MsgBox('ArcVault has been removed.' + #13#10#13#10 +
           'Your collection files and history were kept (normally in Documents\ArcVault). ' +
           'Delete that folder yourself if you don''t need them any more.', mbInformation, MB_OK);
end;
