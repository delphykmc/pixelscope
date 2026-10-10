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
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ManifestFile}"; DestDir: "{app}"; DestName: "release-manifest.json"; Flags: ignoreversion
Source: "{#NoticeFile}"; DestDir: "{app}"; DestName: "THIRD_PARTY_NOTICES.txt"; Flags: ignoreversion

#ifndef SmokeBuild
[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#TargetExeName}"; WorkingDir: "{app}"
#endif

[Run]
#ifdef TargetAppName
Filename: "{app}\{#TargetExeName}"; Description: "Launch {#AppName}"; Flags: postinstall nowait skipifsilent
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

function InitializeSetup: Boolean;
begin
#ifdef SmokeBuild
  Result := True;
#else
  Result := ConfirmExistingInstall;
#endif
end;
