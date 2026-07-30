# Packaging constraints

- The build environment and source target are CPython 3.10.x x64 on Windows.
- The executable builder is **exactly `PyInstaller==5.7`**.
- PyInstaller 6.x is prohibited by internal security and installation policy,
  not merely discouraged.
- Prefer a PyInstaller `onedir` build. Do not silently switch to `onefile`.
- Inno Setup is the planned installer layer after the validated `onedir` output.
- User configuration/data must live outside installed application resources.
- Resource lookup must not depend on the source tree or current working directory.
- Freeze the verified dependency set before packaging and do not change the lock
  during a packaging run.
- Packaging, portable ZIP creation, signing, and installer creation were not
  performed in the MVP phase.
- A clean Windows 10/11 PC smoke test is mandatory before release.
