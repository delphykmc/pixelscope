# PixelScope application identity

The current PixelScope name and visual identity remain provisional until release,
but the repository now has one canonical icon source and deterministic derived
assets. Replace these files together if the product name or release identity
changes.

## Canonical asset layout

All application-icon assets live together under
`src/pixelscope/assets/icons/` so runtime and release tooling consume the same
identity rather than maintaining duplicate copies.

| File | Role |
|---|---|
| `pixelscope.svg` | Editable canonical design source; 512 × 512 view box |
| `pixelscope.png` | 256 × 256 indexed-color runtime application/window icon |
| `pixelscope.ico` | Windows executable, taskbar, shortcut, and future installer icon |

The SVG is the source of truth. Regenerate PNG and ICO outputs from it rather
than hand-editing derived files.

## Visual contract

- Blue-gray rounded-square field aligned with the application palette.
- A simplified image frame identifies image inspection.
- A dominant magnifying scope communicates precise analysis.
- A four-cell pixel grid remains legible at small sizes.
- Broad continuous motion lines communicate speed without fragmented or
  Morse-like marks.
- One amber pixel and one amber motion line preserve a restrained family link to
  the earlier orange CAT application icon.
- No text, font dependency, or third-party logo asset is embedded.

## Size contract

The mark must remain identifiable at 16, 20, 24, 32, 40, 48, 64, 128, and
256 px. `pixelscope.ico` contains one transparent frame for each of those sizes.
The runtime PNG matches the largest required Windows frame so Qt can downsample
it deterministically for smaller window and taskbar contexts.

## Runtime and packaging use

- `pixelscope.app.resources.load_application_icon()` reads PNG bytes through
  `importlib.resources`; lookup does not depend on the working directory or a
  source-tree absolute path.
- `create_application()` assigns the icon to `QApplication`, allowing windows to
  inherit the canonical icon.
- `pyproject.toml` declares SVG, PNG, and ICO files as package data.
- Future PyInstaller and Inno Setup configuration must reference
  `src/pixelscope/assets/icons/pixelscope.ico` rather than creating a second ICO.

Installer creation, code signing, and release-name finalization remain P7 work.

## Validation

Automated checks cover SVG vector structure, PNG format and dimensions, exact ICO
frame sizes, and Qt application-icon loading. Manual Windows review remains
required for:

1. Main-window title bar and Alt+Tab presentation.
2. Taskbar icon in normal and pinned states.
3. 100%, 150%, and 200% display scaling.
4. Light and dark Windows taskbar backgrounds.
5. Future PyInstaller executable and Inno Setup shortcut rendering.
