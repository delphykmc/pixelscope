#ifndef AppVersion
  #error AppVersion must be supplied by scripts/build_installer_release.py
#endif
#ifndef AppFileVersion
  #error AppFileVersion must be supplied by scripts/build_installer_release.py
#endif
#ifndef AppVersionMajor
  #error AppVersionMajor must be supplied by scripts/build_installer_release.py
#endif
#ifndef AppVersionMinor
  #error AppVersionMinor must be supplied by scripts/build_installer_release.py
#endif
#ifndef AppVersionRevision
  #error AppVersionRevision must be supplied by scripts/build_installer_release.py
#endif
#ifndef AppVersionBuild
  #error AppVersionBuild must be supplied by scripts/build_installer_release.py
#endif

#if Ver < 0x06010000
  #error P7-B requires Inno Setup 6.1 or newer
#endif
#if Ver >= 0x08000000
  #error P7-B does not support Inno Setup 8 or newer
#endif

#ifdef TargetAppName
  #define AppName TargetAppName
#else
  #define AppName "PixelScope"
#endif
#ifndef AppIdValue
  #define AppIdValue "{{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}"
#endif
// Defensive compiler-side allowlist: direct ISCC overrides must not turn
// this reusable installer into an arbitrary-product uninstall tool.
#ifdef TargetCorePredecessor
  #if LowerCase(TargetCorePredecessor) != LowerCase("{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}")
    #error Unsupported Core predecessor AppId
  #endif
  #ifndef TargetAppDir
    #error Core conversion requires a distinct downstream folder
  #endif
  #ifndef TargetRegistryAppId
    #error Core conversion requires a distinct downstream AppId
  #endif
  #if LowerCase(TargetRegistryAppId) == LowerCase("{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}")
    #error Downstream AppId must not equal Core
  #endif
#endif
#define RepoRoot AddBackslash(SourcePath) + "..\.."
#ifdef TargetAppSource
  #define AppSource TargetAppSource
#else
  #define AppSource AddBackslash(RepoRoot) + "dist\PixelScope"
#endif
#define ReleaseRoot AddBackslash(RepoRoot) + "release"
#ifdef TargetReleaseStem
  #define ReleaseStem TargetReleaseStem
#else
  #define ReleaseStem "PixelScope-" + AppVersion + "-windows-x64"
#endif
#define ManifestFile AddBackslash(ReleaseRoot) + ReleaseStem + ".manifest.json"
#define NoticeFile AddBackslash(ReleaseRoot) + ReleaseStem + "-THIRD_PARTY_NOTICES.txt"
#define SetupIconFile AddBackslash(RepoRoot) + "src\pixelscope\assets\icons\pixelscope.ico"
#ifndef TargetExeName
  #define TargetExeName "PixelScope.exe"
#endif
#ifdef SmokeBuild
  #define SetupOutputBase ReleaseStem + "-smoke-setup"
#else
  #define SetupOutputBase ReleaseStem + "-setup"
#endif

[Setup]
AppId={#AppIdValue}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PixelScope
VersionInfoVersion={#AppFileVersion}
#ifdef TargetAppDir
DefaultDirName={localappdata}\Programs\{#TargetAppDir}
DefaultGroupName={#AppName}
#else
DefaultDirName={localappdata}\Programs\PixelScope
DefaultGroupName=PixelScope
#endif
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
OutputDir={#ReleaseRoot}
OutputBaseFilename={#SetupOutputBase}
SetupIconFile={#SetupIconFile}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UsePreviousAppDir=yes
Uninstallable=yes
UninstallDisplayIcon={app}\{#TargetExeName}
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no

[Files]
#if defined(TargetCorePredecessor) && !defined(SmokeBuild)
Source: "{#RepoRoot}\packaging\installer\verify_downstream_payload.ps1"; Flags: dontcopy
#endif
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ManifestFile}"; DestDir: "{app}"; DestName: "release-manifest.json"; Flags: ignoreversion
Source: "{#NoticeFile}"; DestDir: "{app}"; DestName: "THIRD_PARTY_NOTICES.txt"; Flags: ignoreversion

#ifndef SmokeBuild
[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#TargetExeName}"; WorkingDir: "{app}"
#endif

[Run]
#ifdef TargetAppName
  #if defined(TargetCorePredecessor) && !defined(SmokeBuild)
Filename: "{app}\{#TargetExeName}"; Description: "Launch {#AppName}"; Flags: postinstall nowait skipifsilent; Check: ShouldOfferLaunch
  #else
Filename: "{app}\{#TargetExeName}"; Description: "Launch {#AppName}"; Flags: postinstall nowait skipifsilent
  #endif
#else
Filename: "{app}\PixelScope.exe"; Description: "Launch PixelScope"; Flags: postinstall nowait skipifsilent
#endif

[Code]
const
#ifdef TargetAppName
  PixelScopeUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#TargetRegistryAppId}_is1';
#else
  PixelScopeUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}_is1';
#endif
  CurrentVersionText = '{#AppVersion}';

function ReadExistingInstall(
  var InstalledVersion: Int64;
  var InstalledVersionText: String;
  var VersionKnown: Boolean
): Boolean;
var
  InstallLocation: String;
  HasInstallLocation: Boolean;
  HasDisplayVersion: Boolean;
  InstalledExecutable: String;
begin
  HasInstallLocation := RegQueryStringValue(
    HKCU64,
    PixelScopeUninstallKey,
    'InstallLocation',
    InstallLocation
  );
  HasDisplayVersion := RegQueryStringValue(
    HKCU64,
    PixelScopeUninstallKey,
    'DisplayVersion',
    InstalledVersionText
  );

  Result := HasInstallLocation or HasDisplayVersion;
  VersionKnown := False;
  if not Result then
    Exit;

  if HasInstallLocation then
  begin
    InstalledExecutable := AddBackslash(InstallLocation) + '{#TargetExeName}';
    VersionKnown := GetPackedVersion(InstalledExecutable, InstalledVersion);
  end;

  if VersionKnown and (not HasDisplayVersion) then
    InstalledVersionText := VersionToStr(InstalledVersion)
  else if not HasDisplayVersion then
    InstalledVersionText := 'unknown';
end;

function ConfirmExistingInstall: Boolean;
var
  InstalledVersion: Int64;
  CurrentVersion: Int64;
  InstalledVersionText: String;
  VersionKnown: Boolean;
  Comparison: Integer;
  PromptText: String;
begin
  Result := True;
  if not ReadExistingInstall(InstalledVersion, InstalledVersionText, VersionKnown) then
    Exit;

  if not VersionKnown then
  begin
    PromptText :=
      'An existing PixelScope installation was found, but its version could not be verified. ' +
      'Continue with PixelScope ' + CurrentVersionText + '?';
    Result := SuppressibleMsgBox(
      PromptText,
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2,
      IDNO
    ) = IDYES;
    Exit;
  end;

  CurrentVersion := PackVersionComponents(
    {#AppVersionMajor},
    {#AppVersionMinor},
    {#AppVersionRevision},
    {#AppVersionBuild}
  );
  Comparison := ComparePackedVersion(InstalledVersion, CurrentVersion);

  if Comparison > 0 then
  begin
    PromptText :=
      'PixelScope ' + InstalledVersionText + ' is already installed, which is newer than ' +
      CurrentVersionText + '. Install the older version anyway?';
    Result := SuppressibleMsgBox(
      PromptText,
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2,
      IDNO
    ) = IDYES;
  end
  else if Comparison = 0 then
  begin
    PromptText :=
      'PixelScope ' + InstalledVersionText + ' is already installed. Reinstall this version?';
    Result := SuppressibleMsgBox(
      PromptText,
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2,
      IDYES
    ) = IDYES;
  end
  else
  begin
    PromptText :=
      'PixelScope ' + InstalledVersionText + ' is installed. Upgrade to ' +
      CurrentVersionText + '?';
    Result := SuppressibleMsgBox(
      PromptText,
      mbConfirmation,
      MB_YESNO,
      IDYES
    ) = IDYES;
  end;
end;

#if defined(TargetCorePredecessor) && !defined(SmokeBuild)
// Enabled only by the validated downstream descriptor and the MAIN builder.
// The known PUBLIC Core GUID is a predecessor, never the downstream AppId.
const
  CoreUninstallKey =
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#TargetCorePredecessor}_is1';
  DownstreamUninstallKey =
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#TargetRegistryAppId}_is1';
  CoreExeName = 'PixelScope.exe';
  ExpectedManifestSha256 = '{#TargetManifestSha256}';
  ExpectedExeSha256 = '{#TargetExeSha256}';
  PartialConversionExitCode = 77;

var
  CoreInstallLocation: String;
  CoreUninstaller: String;
  ConversionRequested: Boolean;
  ConversionFailed: Boolean;

function GetFileAttributesW(Path: String): Cardinal;
  external 'GetFileAttributesW@kernel32.dll stdcall';

function UnsafeReparsePath(Path: String): Boolean;
var
  Attr: Cardinal;
begin
  Attr := GetFileAttributesW(Path);
  Result := (Attr = $FFFFFFFF) or ((Attr and $400) <> 0);
end;

function ConversionSwitchPresent: Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if LowerCase(ParamStr(I)) = '/allowcoreconversion=1' then
    begin
      Result := True;
      Exit;
    end;
end;

function VerifyCoreRegistration(var Failure: String): Boolean;
var
  Location: String;
  UninstallCommand: String;
  DisplayName: String;
  RegisteredVersion: String;
  ExistingVersion: Int64;
  ExpectedLocation: String;
  ExpectedUninstaller: String;
  // LoadStringFromFile requires AnsiString in Unicode Inno Setup 6/7.
  // The generated release manifest is ASCII-safe JSON (escaped non-ASCII).
  CoreManifest: AnsiString;
begin
  Result := False;
  Failure := '';

  // A machine-wide Core installation is outside PUBLIC per-user scope.
  // HKCU uninstall identities may share a WOW64 registry view; do not reject
  // the supported HKCU64 registration just because HKCU32 also sees it.
  if RegKeyExists(HKLM64, CoreUninstallKey) or
     RegKeyExists(HKLM32, CoreUninstallKey) then
  begin
    Failure := 'Core is registered outside the supported HKCU64 per-user scope.';
    Exit;
  end;
  if not RegKeyExists(HKCU64, CoreUninstallKey) then
  begin
    Failure := 'Core uninstall registration disappeared.';
    Exit;
  end;
  if not RegQueryStringValue(HKCU64, CoreUninstallKey, 'InstallLocation', Location) or
     not RegQueryStringValue(HKCU64, CoreUninstallKey, 'UninstallString', UninstallCommand) or
     not RegQueryStringValue(HKCU64, CoreUninstallKey, 'DisplayName', DisplayName) or
     not RegQueryStringValue(HKCU64, CoreUninstallKey, 'DisplayVersion', RegisteredVersion) then
  begin
    Failure := 'Core uninstall registration has missing identity fields.';
    Exit;
  end;
  ExpectedLocation := ExpandConstant('{localappdata}\Programs\PixelScope');
  if CompareText(RemoveBackslashUnlessRoot(Location),
                 RemoveBackslashUnlessRoot(ExpectedLocation)) <> 0 then
  begin
    Failure := 'Core install location is not the supported PUBLIC layout.';
    Exit;
  end;
  // Inno defaults UninstallDisplayName to AppVerName, which includes the
  // registered AppVersion. Preserve support for an older name-only entry.
  if (RegisteredVersion = '') or
     ((CompareText(DisplayName, 'PixelScope ' + RegisteredVersion) <> 0) and
      (CompareText(DisplayName, 'PixelScope') <> 0)) then
  begin
    Failure := 'Core uninstall DisplayName does not match PUBLIC Core identity.';
    Exit;
  end;
  ExpectedUninstaller := AddBackslash(Location) + 'unins000.exe';
  if UnsafeReparsePath(Location) or
     UnsafeReparsePath(ExtractFileDir(Location)) or
     UnsafeReparsePath(ExpectedUninstaller) or
     UnsafeReparsePath(ChangeFileExt(ExpectedUninstaller, '.dat')) or
     UnsafeReparsePath(AddBackslash(Location) + CoreExeName) then
  begin
    Failure := 'Core install path contains a missing item or unsafe reparse point.';
    Exit;
  end;
  if CompareText(RemoveQuotes(UninstallCommand), ExpectedUninstaller) <> 0 then
  begin
    Failure := 'Core registered uninstaller is not the expected owned executable.';
    Exit;
  end;
  if not FileExists(ExpectedUninstaller) or
     not FileExists(ChangeFileExt(ExpectedUninstaller, '.dat')) or
     not FileExists(AddBackslash(Location) + CoreExeName) or
     not GetPackedVersion(AddBackslash(Location) + CoreExeName, ExistingVersion) then
  begin
    Failure := 'Core installed executable, version or uninstaller is invalid.';
    Exit;
  end;

  // The manifest is optional for older installations but must be coherent
  // when present. Never follow arbitrary paths from its contents.
  if FileExists(AddBackslash(Location) + 'release-manifest.json') then
  begin
    if not LoadStringFromFile(
        AddBackslash(Location) + 'release-manifest.json', CoreManifest) or
       (Pos('"product": "PixelScope"', String(CoreManifest)) = 0) then
    begin
      Failure := 'Core release-manifest.json does not identify PUBLIC Core.';
      Exit;
    end;
  end;
  CoreInstallLocation := Location;
  CoreUninstaller := ExpectedUninstaller;
  Result := True;
end;

function CoreIsNotRunning: Boolean;
var
  PS: String;
  Args: String;
  ExitCode: Integer;
begin
  // A process check is mandatory before installation AND prior to removal.
  // Missing/blocked PowerShell is treated as unsafe; never force-terminate.
  PS := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Args := '-NoProfile -NonInteractive -Command ' +
    '"if (Get-Process -Name PixelScope -ErrorAction SilentlyContinue) ' +
    '{ exit 21 } else { exit 0 }"';
  Result := FileExists(PS) and
    Exec(PS, Args, '', SW_HIDE, ewWaitUntilTerminated, ExitCode) and
    (ExitCode = 0);
  if not Result then
    Log('Conversion preflight: Core process check refused (running or unavailable).');
end;

function PrepareCoreConversion: Boolean;
var
  Failure: String;
begin
  Result := True;
  // HKCU32 and HKCU64 can refer to the same per-user uninstall key.
  if RegKeyExists(HKLM64, CoreUninstallKey) or
     RegKeyExists(HKLM32, CoreUninstallKey) then
  begin
    Log('Core conversion blocked: machine-wide or unsupported registration detected.');
    Result := False;
    Exit;
  end;
  if not RegKeyExists(HKCU64, CoreUninstallKey) then
    Exit;

  // A positive opt-in is required even in /VERYSILENT /SUPPRESSMSGBOXES.
  // Missing consent aborts Setup before new files or registry entries.
  if WizardSilent then
    Result := ConversionSwitchPresent
  else
    Result := SuppressibleMsgBox(
      'Convert the existing PUBLIC PixelScope Core installation to ' +
      '{#AppName}' + '?' + #13#10 +
      'The new edition will be installed and verified first. Core will only ' +
      'then be uninstalled. Your user settings are retained.' + #13#10 +
      'If conversion fails, both editions may remain; review the installer log.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO
    ) = IDYES;
  if not Result then
  begin
    Log('Core conversion not authorized: setup aborted without mutation.');
    Exit;
  end;
  if not VerifyCoreRegistration(Failure) or not CoreIsNotRunning then
  begin
    Log('Core conversion preflight failed: ' + Failure);
    Result := False;
    Exit;
  end;
  ConversionRequested := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Failure: String;
  CanonicalDownstream: String;
begin
  Result := '';
  if not ConversionRequested then
    Exit;
  // Disallow /DIR re-targeting into Core or any user-controlled install root
  // during conversion. Fresh installations retain ordinary folder selection.
  CanonicalDownstream := ExpandConstant('{localappdata}\Programs\{#TargetAppDir}');
  if CompareText(RemoveBackslashUnlessRoot(WizardDirValue),
                 RemoveBackslashUnlessRoot(CanonicalDownstream)) <> 0 then
  begin
    Result := 'Core conversion requires the default separate downstream install folder.';
    Exit;
  end;
  if DirExists(CanonicalDownstream) and UnsafeReparsePath(CanonicalDownstream) then
  begin
    Result := 'Downstream install directory is a reparse point; conversion refused.';
    Exit;
  end;
  if not VerifyCoreRegistration(Failure) then
  begin
    Result := 'Core registration changed during setup: ' + Failure;
    Exit;
  end;
  if not CoreIsNotRunning then
    Result := 'Core is running, or the process check is unavailable. Close Core and retry.';
end;

function VerifyInstalledPayload: Boolean;
var
  PS: String;
  Args: String;
  ExitCode: Integer;
begin
  Result := False;
  PS := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  if not FileExists(PS) then
  begin
    Log('Conversion withheld: offline payload verifier is unavailable.');
    Exit;
  end;
  try
    // This script is compiled into the trusted Setup, not loaded from a
    // downloaded/private location. It checks every manifest-owned file,
    // path containment, reparse safety, size and SHA-256.
    ExtractTemporaryFile('verify_downstream_payload.ps1');
    Args := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
      ExpandConstant('{tmp}\verify_downstream_payload.ps1') + '"' +
      ' -InstallRoot "' + ExpandConstant('{app}') + '"' +
      ' -ExpectedProduct "{#AppName}"' +
      ' -ExpectedVersion "{#AppVersion}"' +
      ' -ExpectedExeName "{#TargetExeName}"';
    if not Exec(PS, Args, '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    begin
      Log('Conversion withheld: payload verification process could not start.');
      Exit;
    end;
    Result := ExitCode = 0;
    if not Result then
      Log('Conversion withheld: full payload manifest verification failed with ' +
          'exit code ' + IntToStr(ExitCode));
  except
    Log('Conversion withheld: payload verifier exception: ' + GetExceptionMessage);
    Result := False;
  end;
end;

function VerifyDownstreamReadiness: Boolean;
var
  InstalledVersion: Int64;
  ExpectedVersion: Int64;
  ManifestFile: String;
  ExecutableFile: String;
  DownstreamLocation: String;
begin
  Result := False;
  // ssDone is after installation; require a distinct registered edition.
  if not RegKeyExists(HKCU64, DownstreamUninstallKey) then
  begin
    Log('Conversion withheld: downstream registration missing.');
    Exit;
  end;
  if not RegQueryStringValue(HKCU64, DownstreamUninstallKey,
      'InstallLocation', DownstreamLocation) or
     (CompareText(RemoveBackslashUnlessRoot(DownstreamLocation),
                  RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) <> 0) then
  begin
    Log('Conversion withheld: downstream registration points outside the install root.');
    Exit;
  end;
  ManifestFile := ExpandConstant('{app}\release-manifest.json');
  ExecutableFile := ExpandConstant('{app}\{#TargetExeName}');
  if not FileExists(ManifestFile) or not FileExists(ExecutableFile) then
  begin
    Log('Conversion withheld: downstream manifest or executable missing.');
    Exit;
  end;
  // PascalScript evaluates boolean operators before <>; bracket each comparison.
  if (CompareText(GetSHA256OfFile(ManifestFile), ExpectedManifestSha256) <> 0) or
     (CompareText(GetSHA256OfFile(ExecutableFile), ExpectedExeSha256) <> 0) then
  begin
    Log('Conversion withheld: downstream manifest or executable SHA-256 mismatch.');
    Exit;
  end;
  ExpectedVersion := PackVersionComponents(
    {#AppVersionMajor}, {#AppVersionMinor},
    {#AppVersionRevision}, {#AppVersionBuild}
  );
  if (not GetPackedVersion(ExecutableFile, InstalledVersion)) or
     (ComparePackedVersion(InstalledVersion, ExpectedVersion) <> 0) then
  begin
    Log('Conversion withheld: downstream executable FileVersion mismatch.');
    Exit;
  end;
  Result := VerifyInstalledPayload;
end;

function UninstallVerifiedCore: Boolean;
var
  Failure: String;
  ExitCode: Integer;
  I: Integer;
begin
  Result := False;
  // Revalidate immediately before removal; fail on changed identity or a
  // newly running Core. Never uninstall an unverified arbitrary path.
  if not VerifyCoreRegistration(Failure) or not CoreIsNotRunning then
  begin
    Log('Conversion withheld before Core uninstall: ' + Failure);
    Exit;
  end;
  if not Exec(CoreUninstaller,
      '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART',
      CoreInstallLocation, SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    Log('Core uninstaller could not be started. Win32 code: ' + IntToStr(ExitCode));
    Exit;
  end;
  if ExitCode <> 0 then
  begin
    Log('Core uninstall returned error: ' + IntToStr(ExitCode));
    Exit;
  end;
  // Inno uninstaller cleanup may be deferred briefly after child exit.
  for I := 0 to 40 do
  begin
    if not RegKeyExists(HKCU64, CoreUninstallKey) and
       not FileExists(AddBackslash(CoreInstallLocation) + CoreExeName) and
       not FileExists(CoreUninstaller) then
    begin
      Result := True;
      Exit;
    end;
    Sleep(250);
  end;
  Log('Core uninstaller exited but owned files/registration remain.');
end;

function ShouldOfferLaunch: Boolean;
begin
  // No postinstall launch until migration has been resolved.
  Result := not ConversionRequested;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Completed: Boolean;
begin
  if (CurStep <> ssDone) or not ConversionRequested then
    Exit;
  Completed := False;
  try
    // Never evaluate Core uninstall unless all downstream checks pass.
    if VerifyDownstreamReadiness then
      Completed := UninstallVerifiedCore;
  except
    Log('PARTIAL CONVERSION verification exception: ' + GetExceptionMessage);
    Completed := False;
  end;
  if not Completed then
  begin
    ConversionFailed := True;
    Log('PARTIAL CONVERSION: downstream installed; Core retained or uncertain. ' +
        'Do not claim migration success. Retry/repair after checking setup log.');
    SuppressibleMsgBox(
      'PixelScope conversion is incomplete. The new edition was installed, ' +
      'but Core removal could not be verified. Both editions may remain.' + #13#10 +
      'Check the installer log and retry/repair manually.',
      mbError, MB_OK, IDOK
    );
  end
  else
    Log('Verified Core-to-downstream conversion completed.');
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := 0;
  if ConversionFailed then
    Result := PartialConversionExitCode;
end;
#endif

function InitializeSetup: Boolean;
begin
#ifdef SmokeBuild
  Result := True;
#else
  Result := ConfirmExistingInstall;
  #if defined(TargetCorePredecessor) && !defined(SmokeBuild)
    if Result then
      Result := PrepareCoreConversion;
  #endif
#endif
end;
