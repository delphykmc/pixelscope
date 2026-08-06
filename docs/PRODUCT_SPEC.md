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
- Fixed two/three/four/five/six-image layouts with focus promotion in three and
  five views.
- Structured status for active file, format/resolution, coordinate, pixel value,
  zoom, and background work.
- Statistics with explicit image/channel fields and full-image/ROI scope.
- Histogram Auto/256/1024/4096 bins with Count, Normalized, and Log count.
- Horizontal/vertical Line Profile with explicit reference selection in
  Difference-from-reference mode.
- RGB and Bayer R/Gr/Gb/B analysis; RGBA alpha is ignored.
- Order-independent native absolute Difference cache with Absolute/Mask display,
  ROI metrics, LRU eviction, and diagnostics.
- Resizable, collapsible, floating, and maximizable Plots dock.
- Persisted main geometry, dock state, splitters, last directory, layout,
  analysis state, and selected Plots tab.

A seventh derived Difference result is shown in Single View when all six source
positions are occupied.

## RAW contract

RAW opens through a validated profile workflow. A same-name JSON sidecar can
pre-fill the profile; the user preference may skip repeated confirmation for
those JSON profiles. The same RAW path may be reloaded with corrected settings.

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

The complete product adds performance Preferences, byte-budgeted source
residency and preload, RAW demosaic/normalization/profile suggestion, alpha
overlay, persistent sessions and ROI management, live GPU IQA/image evaluation,
heatmaps, and a validated standalone Windows distribution.
