#ifndef AppVersion
  #error AppVersion must be supplied by scripts/build_installer_release.py
#endif
#ifndef AppFileVersion
  #error AppFileVersion must be supplied by scripts/build_installer_release.py
#endif
#ifndef AppSource
  #error AppSource must be supplied by scripts/build_installer_release.py
#endif
#ifndef ManifestFile
  #error ManifestFile must be supplied by scripts/build_installer_release.py
#endif
#ifndef NoticeFile
  #error NoticeFile must be supplied by scripts/build_installer_release.py
#endif
#ifndef OutputDir
  #error OutputDir must be supplied by scripts/build_installer_release.py
#endif
#ifndef OutputBaseFilename
  #error OutputBaseFilename must be supplied by scripts/build_installer_release.py
#endif
#ifndef SetupIconFile
  #error SetupIconFile must be supplied by scripts/build_installer_release.py
#endif

#define AppName "PixelScope"

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
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
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
