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

- Blue-gray rounded-square field aligned with the application palette.
- A simplified image frame identifies image inspection.
- A dominant magnifying scope communicates precise analysis.
- A four-cell pixel grid remains legible at small sizes.
- Broad continuous motion lines communicate speed without fragmented or
  Morse-like marks.
- One amber pixel and one amber motion line preserve a restrained family link to
  the earlier orange CAT application icon.
- No text, font dependency, rendered raster element, or third-party logo is
  embedded in the SVG.

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

The first command rewrites the derived files. The second command renders again
and fails unless the checked-in PNG and ICO exactly match the canonical SVG,
renderer, alpha handling, frame sizes, and frame order. Review the 16–48 px
outputs visually whenever the SVG changes; automatic downscaling is not a
substitute for small-size legibility review.

## Runtime and packaging use

- `pixelscope.app.resources.load_application_icon()` reads PNG bytes through
  `importlib.resources`; lookup does not depend on the working directory or a
  source-tree absolute path.
- `create_application()` assigns the icon to `QApplication`, allowing windows to
  inherit the canonical runtime icon.
- `pyproject.toml` declares SVG, PNG, and ICO files as package data.
- Future PyInstaller and Inno Setup definitions must bind the canonical ICO
  rather than creating a second copy.

Verify wheel contents after any package-data or asset change:

```powershell
Remove-Item -Recurse -Force .tmp-wheel -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pip wheel . --no-deps -w .tmp-wheel
.\.venv\Scripts\python.exe scripts\check_wheel_icon_assets.py .tmp-wheel
```

Executable-file icons, pinned shortcuts, installer shortcuts, AppUserModelID
policy, signing, and release-name finalization remain P7 work.

## P2-A1 manual validation

For the source-run identity/resource slice, verify on Windows:

1. Launch from the repository root and from an unrelated working directory.
2. Main-window title bar and Alt+Tab icon.
3. Running taskbar icon.
4. 100%, 150%, and 200% display scaling.
5. Light and dark taskbar backgrounds.

Pinned shortcut, executable-file, installer-shortcut, and final packaged-shell
identity checks are intentionally deferred to P7.
