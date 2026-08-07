# Product specification

PixelScope is a CPU-only Windows engineering tool for rapid visual and numeric
comparison of PNG, BMP, JPEG, and profile-described RAW images. The workflow is
selection-driven rather than fixed A/B: register files or folders, select up to
six sources, inspect them in Single or Multi View, and compare full-image or ROI
results.

## Implemented workflow

- Folder-grouped Files tree with drag-and-drop, context actions, natural order,
  and loading/resident/error indicators.
- Ordered multi-selection and atomic Page Up/Page Down folder navigation.
- Auto, Single, and Multi View with synchronized cursor, zoom, offset, ROI, and
  line coordinates.
- Fixed two/three/four/five/six-image layouts with primary-image ordering for
  every Multi View containing at least two images.
- The first displayed image is the implicit primary. Selecting another primary
  moves it to the first tile without changing Files selection order or logical
  image IDs.
- Two-, four-, and six-image layouts retain equal tile sizes; three- and
  five-image layouts enlarge the first, primary tile.
- Structured status for active file, format/resolution, coordinate, pixel value,
  zoom, and background work.
- Statistics with explicit image/channel fields and full-image/ROI scope.
- Histogram Auto/256/1024/4096 bins with Count, Normalized, and Log count.
- Horizontal/vertical Line Profile with explicit reference selection in
  Difference-from-reference mode. Reference priority starts with the primary
  image, then the active image, then the first displayed image.
- RGB and Bayer R/Gr/Gb/B analysis; RGBA alpha is ignored.
- Order-independent native absolute Difference cache with Absolute/Mask display,
  ROI metrics, LRU eviction, diagnostics, and a startup-configurable byte budget.
- Resizable, collapsible, floating, and maximizable Plots dock.
- Persisted main geometry, dock state, splitters, last directory, layout,
  analysis state, and selected Plots tab.
- `Edit > Settings...` uses **General / Files / Performance** category pages.
- General owns the persistent RAW JSON confirmation preference; it is not
  duplicated in the File menu.
- Files provides optional Default Open Folder and Default Export Folder values.
  Blank preserves the remembered last-used-folder behavior; configured existing
  folders only seed dialog starting locations and apply without restart.
- Performance owns Difference Cache. It defaults to 512 MiB, accepts 64–8192
  MiB, and applies a changed value after PixelScope restarts. The current runtime
  cache is not resized live.
- `Reset Settings` restores application preferences without resetting workspace
  layout, window geometry, dock/splitter state, or remembered last-directory
  state.
- Exact docking/layout values remain workspace state rather than configurable
  defaults because the saved workspace is already authoritative.

A seventh derived Difference result is shown in Single View when all six source
positions are occupied.

## RAW contract

RAW opens through a validated profile workflow. A same-name JSON sidecar can
pre-fill the profile; the General Settings preference may skip repeated
confirmation for those JSON profiles. The RAW dialog's explicit don't-show-again
choice persists the same typed preference. The same RAW path may be reloaded with
corrected settings.

The profile separates:

- storage format: unpacked, MIPI RAW10, RAW12, or RAW14
- sample container for unpacked data: `uint8` or `uint16`
- effective bit depth
- byte order and LSB/MSB alignment where applicable
- width, height, offset, stride, and grayscale/Bayer layout

Packed formats own their byte layout and fixed bit depth, so container,
endianness, and alignment controls do not apply. Bayer is analyzed as native
mosaic planes; demosaic is outside the current product contract.

## Future product scope

The complete product adds byte-budgeted decoded-source residency and preload,
RAW demosaic/normalization/profile suggestion, alpha overlay, persistent
sessions and ROI management, live GPU IQA/image evaluation, heatmaps, and a
validated standalone Windows distribution.
