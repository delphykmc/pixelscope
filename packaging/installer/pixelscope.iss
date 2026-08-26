#ifndef AppVersion
  #error AppVersion must be supplied by scripts/build_installer_release.py
#endif
#ifndef AppFileVersion
  #error AppFileVersion must be supplied by scripts/build_installer_release.py
#endif

#define AppName "PixelScope"
#define RepoRoot AddBackslash(SourcePath) + "..\.."
#define AppSource AddBackslash(RepoRoot) + "dist\PixelScope"
#define ReleaseRoot AddBackslash(RepoRoot) + "release"
#define ReleaseStem "PixelScope-" + AppVersion + "-windows-x64"
#define ManifestFile AddBackslash(ReleaseRoot) + ReleaseStem + ".manifest.json"
#define NoticeFile AddBackslash(ReleaseRoot) + ReleaseStem + "-THIRD_PARTY_NOTICES.txt"
#define SetupIconFile AddBackslash(RepoRoot) + "src\pixelscope\assets\icons\pixelscope.ico"

[Setup]
AppId={{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PixelScope
VersionInfoVersion={#AppFileVersion}
DefaultDirName={localappdata}\Programs\PixelScope
DefaultGroupName=PixelScope
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
OutputDir={#ReleaseRoot}
OutputBaseFilename={#ReleaseStem}-setup
SetupIconFile={#SetupIconFile}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UsePreviousAppDir=yes
Uninstallable=yes
UninstallDisplayIcon={app}\PixelScope.exe
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ManifestFile}"; DestDir: "{app}"; DestName: "release-manifest.json"; Flags: ignoreversion
Source: "{#NoticeFile}"; DestDir: "{app}"; DestName: "THIRD_PARTY_NOTICES.txt"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\PixelScope"; Filename: "{app}\PixelScope.exe"; WorkingDir: "{app}"
