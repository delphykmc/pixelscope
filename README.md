# PixelScope

PixelScope is a CPU-only Windows image inspection and comparison tool for PNG,
BMP, JPEG, and profile-described RAW images.

The application is designed around native image data: decoded source pixels remain
authoritative for inspection and analysis, while viewer transforms such as Display
Gain are presentation-only.

## Core workflow

PixelScope distinguishes four states:

```text
Registered -> Selected -> Presented -> Resident when required
```

- **Registered** images are known to the Files workspace/catalog.
- **Selected** images form the current comparison/analysis set.
- **Presented** images occupy viewer tiles; the current viewer supports at most six
  source images simultaneously.
- **Resident** images currently retain decoded native source under the source-memory
  budget.

The six-tile viewer capacity does not limit workspace registration.

### Open images

Use **File > Open Images...** (`Ctrl+O`) to open one or more supported image files:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

Directly opened files are registered and selected for viewing. Ordinary images and
RAW share the same user-facing command; RAW profile resolution remains
format-specific internally.

### Open folders

Use **File > Open Folders...** (`Ctrl+Shift+O`) to register one or more image
folders. Folder input is registration-oriented: supported contents are added to
Files without changing the current selection or viewer presentation. Folder count
is not limited to six and no first image is selected automatically.

Drag/drop follows the same intent: direct image files are registered and selected;
folders are registration-only. Mixed file + folder drops select only the directly
dropped files.

## Current capabilities

- Fixed one-to-six-image Single/Multi View layouts with synchronized cursor,
  zoom/pan, ROI, and line coordinates.
- Files workspace with natural ordering, multi-selection, Folder Position
  PageUp/PageDown navigation, and decoded-source residency indicators.
- Statistics and Histogram over native source pixels.
- Line Profile with shared horizontal/vertical selection.
- Difference for Gray, RGB/RGBA, and same-CFA Bayer, including mixed effective bit
  depth normalization.
- Split-channel views for RGB/RGBA and Bayer.
- Display Gain 1×/2×/4×/8×/16× for ordinary and RAW presentation without changing
  native analysis data.
- Profile-described RAW support for unpacked uint8/uint16 and MIPI RAW10/12/14,
  including stride/offset/endian/alignment, Gray/Bayer layout, Bayer pattern,
  Black Level, White Level, and exact/minimum file-size policy.
- Byte-budgeted decoded-source residency, independent Difference cache, bounded
  next-Folder-Position preload, and deterministic sanitized runtime diagnostics.
- Typed versioned application Settings separated from workspace layout persistence.

## RAW profile workflow

For a directly opened/dropped RAW file, PixelScope first looks for an exact
same-basename JSON sidecar. A valid sidecar follows the configured confirmation and
file-size policy; missing or invalid metadata uses the editable RAW Profile dialog.
Cancelling direct RAW profile entry prevents that RAW from being registered.

RAW files discovered through folder registration are kept pending without forcing
a sequence of profile dialogs. Their profile is resolved when foreground
selection/loading actually needs the source. Unresolved RAW is not speculatively
preloaded and PixelScope does not guess profile parameters from file size.

The dialog uses **Load Profile...** / **Save Profile...** terminology; JSON remains
the compatible storage format.

## Development

PixelScope targets CPython 3.10 x64. Install the pinned runtime/development
dependencies from the repository requirements and run the application from the
repository root.

Standard validation is documented in [`docs/QUALITY.md`](docs/QUALITY.md). The
repository owner runs the Windows `.venv` validation contract before merge.

Durable product and architecture documentation lives under [`docs/`](docs/), with
the active execution plan at
[`docs/exec-plans/active/next-phase.md`](docs/exec-plans/active/next-phase.md).
