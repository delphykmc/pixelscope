# PixelScope application identity

The current PixelScope name and visual identity remain provisional until release,
but the repository has one canonical icon source and one reproducible generation
path for its runtime and Windows derivatives. Replace the complete triplet if the
product name or release identity changes.

## Canonical asset layout

All application-icon assets live under `src/pixelscope/assets/icons/` so runtime
and release tooling consume the same identity rather than maintaining duplicate
copies.

| File | Role |
|---|---|
| `pixelscope.svg` | Editable canonical vector source; 512 × 512 view box |
| `pixelscope.png` | Transparent 256 × 256 Qt runtime application/window icon |
| `pixelscope.ico` | Future Windows executable, shortcut, and installer shell icon |

The SVG is the source of truth. Do not hand-edit the PNG or ICO.

## Visual contract

- The icon is a standalone transparent mark without a full-canvas background,
  rounded-square plate, or enclosing application tile.
- A large white photograph frame with a simplified sun-and-mountain scene makes
  the image-inspection domain immediately recognizable.
- A dominant magnifying scope overlaps the photograph and communicates precise
  inspection rather than generic image viewing.
- A coarse five-by-five pixel mosaic inside the lens communicates pixel-level
  analysis and remains recognizable after taskbar downscaling.
- Dark navy outlines, white/silver structural elements, and medium blue-gray
  fills provide clear contrast on both light and dark Windows taskbars.
- A compact amber region in the pixel mosaic and an amber handle collar preserve
  a restrained visual link to the earlier orange CAT application icon.
- The mark occupies most of the 512 × 512 canvas while retaining transparent
  outer margins for Windows and Qt rendering.
- No text, font dependency, rendered raster element, full-canvas background, or
  third-party logo is embedded in the SVG.

## Size contract

The mark must remain identifiable at 16, 20, 24, 32, 40, 48, 64, 128, and
256 px. `pixelscope.ico` contains one transparent PNG frame for each size in that
ascending order. The runtime PNG is the 256 px render used by Qt.

## Reproducible generation

`scripts/generate_icon_assets.py` is the only supported derivative generator. It
uses the repository-pinned `PySide6==6.4.2` Qt SVG renderer, renders onto a
transparent ARGB32 image, writes `pixelscope.png` from the 256 px frame, and
assembles the ICO from the nine ordered PNG payloads.

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\generate_icon_assets.py
.\.venv\Scripts\python.exe scripts\generate_icon_assets.py --check
```

The first command rewrites the derived files from the SVG. The second command
validates the SVG source, PNG decode/dimensions/transparency, and every ICO
frame's dimensions, payload bounds, transparency, and ascending order without
rewriting files. Review the 16–48 px outputs visually whenever the SVG changes;
automatic downscaling is not a substitute for small-size legibility review.

## Runtime and packaging use

- `pixelscope.app.resources.load_application_icon()` reads PNG bytes through
  `importlib.resources`; lookup does not depend on the working directory or a
  source-tree absolute path.
- `create_application()` assigns the icon to `QApplication`, allowing windows to
  inherit the canonical runtime icon.
- On Windows, `_set_windows_app_user_model_id()` assigns the stable
  `PixelScope.PixelScope` process identity before `QApplication` creation. This
  prevents source-run windows from remaining grouped under the Python shell icon.
- `main()` also assigns the application icon directly to the main window before
  it is shown.
- `pyproject.toml` declares SVG, PNG, and ICO files as package data.
- Future PyInstaller and Inno Setup definitions must bind the canonical ICO
  rather than creating a second copy.

Verify wheel contents after any package-data or asset change:

```powershell
Remove-Item -Recurse -Force .tmp-wheel -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pip wheel . --no-deps -w .tmp-wheel
.\.venv\Scripts\python.exe scripts\check_wheel_icon_assets.py .tmp-wheel
```

Executable-file icons, pinned shortcuts, installer shortcuts, signing, and
release-name finalization remain P7 work. The source-run Windows AppUserModelID
is part of P2-A1 because manual validation demonstrated that it is required for
the running taskbar icon.

## P2-A1 manual validation

For the source-run identity/resource slice, verify on Windows:

1. Launch from the repository root and from an unrelated working directory.
2. Main-window title bar and Alt+Tab icon.
3. Running taskbar icon and separation from the Python process identity.
4. Confirm the mark is large, high-contrast, and recognizable at taskbar size.
5. Verify 100%, 150%, and 200% display scaling.
6. Verify light and dark taskbar backgrounds.

Pinned shortcut, executable-file, installer-shortcut, and final packaged-shell
identity checks are intentionally deferred to P7.
