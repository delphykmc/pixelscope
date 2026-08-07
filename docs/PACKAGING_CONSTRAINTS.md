# Packaging constraints

- The build environment and source target are CPython 3.10.x x64 on Windows.
- The executable builder is **exactly `PyInstaller==5.7`**.
- PyInstaller 6.x is prohibited by internal security and installation policy,
  not merely discouraged.
- Prefer a PyInstaller `onedir` build. Do not silently switch to `onefile`.
- Inno Setup is the planned installer layer after the validated `onedir` output.
- User configuration/data must live outside installed application resources.
- Resource lookup must not depend on the source tree or current working directory.
- Canonical application-icon assets live at
  `src/pixelscope/assets/icons/pixelscope.{svg,png,ico}` and are included as
  package data. Do not maintain a duplicate release icon elsewhere.
- `scripts/generate_icon_assets.py` is the supported path for deriving PNG and
  ICO from the canonical SVG. The pinned PySide6 6.4.2 renderer, transparent
  ARGB32 canvas, frame sizes, and ascending ICO frame order are part of the
  reproducibility contract.
- Runtime icon loading reads packaged PNG bytes through `importlib.resources`.
- Windows source runs assign `PixelScope.PixelScope` as the process
  AppUserModelID before `QApplication` creation, then assign the canonical icon
  to both `QApplication` and the main window. This source-run shell identity is a
  P2-A1 runtime requirement, not a substitute for packaged executable metadata.
- The Windows ICO contains transparent 16, 20, 24, 32, 40, 48, 64, 128, and
  256 px frames. Future PyInstaller and Inno Setup definitions must use that ICO.
- A wheel/package-content smoke check must verify the SVG, PNG, and ICO are
  present and nonempty before an identity/resource PR is complete.
- Executable-file icon binding, pinned shortcuts, installer shortcuts, final
  packaged-shell grouping, signing, and release naming remain P7.
- Freeze the verified dependency set before packaging and do not change the lock
  during a packaging run.
- Packaging, portable ZIP creation, signing, and installer creation were not
  performed in the MVP phase.
- A clean Windows 10/11 PC smoke test is mandatory before release.
