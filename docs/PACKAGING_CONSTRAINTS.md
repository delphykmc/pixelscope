# Packaging constraints

- The Windows release build environment is CPython `>=3.10.8,<3.11` x64.
- The executable builder is **exactly `PyInstaller==5.7`**.
- PyInstaller 6.x is prohibited by internal security and installation policy,
  not merely discouraged.
- The canonical executable build is PyInstaller `onedir`. Do not switch to `onefile`.
- Release/build-only dependencies live in `requirements/release.txt`; PyInstaller is
  not an application runtime dependency. The PyInstaller 5.7-era hook/tool dependency
  set is pinned rather than resolved to arbitrary future releases.
- The release version authority is
  `src/pixelscope/version.py::__version__`. Python package metadata, executable
  metadata, and future ZIP/installer/tag/update metadata must derive from it.
- The canonical PyInstaller spec is `packaging/pixelscope.spec` and reuses
  `src/pixelscope/__main__.py`, which delegates to the existing
  `pixelscope.app.application.main` composition root. Do not add a second application
  bootstrap for packaging.
- Canonical generated paths are `build/pyinstaller/` for PyInstaller work files,
  `build/release/` for generated release metadata, and `dist/PixelScope/` for the
  validated `onedir` tree. These locations are ignored and must not write generated
  content into `src/pixelscope/`.
- `scripts/build_release.py` is the canonical Windows build entry. It rejects
  non-Windows, non-x64, Python outside `>=3.10.8,<3.11`, and PyInstaller versions other
  than 5.7; it generates executable version metadata, runs the spec, and then runs
  structural artifact validation.
- `scripts/validate_release_artifact.py` validates the canonical onedir structure,
  application icon resources, Python/Qt/PySide6/NumPy/OpenCV runtime components, and
  absence of top-level source/dev-tree leakage.
- `scripts/smoke_packaged_release.py` is the Windows executable smoke harness. It
  launches the real `PixelScope.exe`, waits for the process-owned visible PixelScope
  window, requests normal close, and requires bounded clean termination. It does not
  add test-only behavior to the production application.
- Inno Setup is the planned installer layer after the validated `onedir` output.
  Portable ZIP and Inno Setup must consume that same validated tree rather than
  rebuilding the application independently.
- User configuration/data must live outside installed application resources.
- Resource lookup must not depend on the source tree or current working directory.
- Canonical application-icon assets live at
  `src/pixelscope/assets/icons/pixelscope.{svg,png,ico}` and are included as
  package data. Do not maintain a duplicate release icon elsewhere.
- `scripts/generate_icon_assets.py` is the supported path for deriving PNG and
  ICO from the canonical SVG. Asset generation uses the dev-pinned
  `resvg_py==0.3.3` and `Pillow==12.3.0`; those packages are build/development
  dependencies and are not required by the runtime application.
- `scripts/generate_icon_assets.py --check` must regenerate PNG/ICO into a
  temporary directory, compare them byte-for-byte with the checked-in canonical
  derivatives, fail on any mismatch, and clean the temporary output afterward.
- Runtime icon loading reads packaged PNG bytes through `importlib.resources`.
- Windows source runs assign `PixelScope.PixelScope` as the process
  AppUserModelID before `QApplication` creation, then assign the canonical icon
  to both `QApplication` and the main window. This source-run shell identity is a
  P2-A1 runtime requirement, not a substitute for packaged executable metadata.
- The Windows ICO contains transparent 16, 20, 24, 32, 40, 48, 64, 128, and
  256 px frames. PyInstaller uses that ICO; future Inno Setup definitions must use the
  same canonical asset.
- A wheel/package-content smoke check must verify the SVG, PNG, and ICO are
  present and nonempty before an identity/resource PR is complete.
- Pinned/installer shortcuts, final installed-shell grouping, production signing, and
  final release publication remain later P7 work.
- Freeze the verified dependency set before packaging and do not change the lock
  during a packaging run.
- Third-party redistribution/license notices must be resolved before P7-B produces
  distributable portable ZIP or installer artifacts.
- A clean Windows 10/11 PC smoke test is mandatory before final release.

## P7-A Windows validation

Create a release-only environment so release-tool pins do not alter the normal
repository development environment:

```powershell
py -3.10 -m venv .venv-release
.\.venv-release\Scripts\python.exe -m pip install -r requirements\release.txt
.\.venv-release\Scripts\python.exe scripts\build_release.py
.\.venv-release\Scripts\python.exe scripts\validate_release_artifact.py
.\.venv-release\Scripts\python.exe scripts\smoke_packaged_release.py
```

`scripts/build_release.py` already invokes structural artifact validation after a
successful PyInstaller build. Running the validator explicitly afterward is retained
as a clear owner/reviewer evidence step.
