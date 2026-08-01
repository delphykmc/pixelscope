# Product specification

PixelScope is a CPU-only Windows engineering tool for rapid visual and numeric
comparison of multiple PNG, BMP, JPEG, and profile-described unpacked RAW
images. The primary workflow is selection-driven rather than fixed A/B:
register files or folders, select up to six sources, inspect them in Single or
Multi View, and compare full-image or ROI results.

## Implemented workflow

- Folder-grouped Files tree with drag-and-drop and context actions.
- Ordered multi-selection and atomic Page Up/Page Down folder navigation.
- Auto, Single, and Multi View with synchronized cursor, zoom, offset, ROI, and
  line coordinates.
- Smart 2/3/4/5/6-image layouts and push-order reference promotion.
- Structured status fields for active file, format/resolution, coordinate,
  pixel value, zoom, and background work.
- One statistics row per image/channel with explicit Id and Ch fields.
- Separate/Overlay and Count/Normalized histograms with native or 0–1 range.
- Horizontal/vertical line profiles selected from the longer Alt-drag axis.
- RGB analysis and unpacked Bayer R/Gr/Gb/B planes; RGBA alpha is ignored.
- Order-independent cached native absolute Difference with Absolute/Mask
  display and Full image/Active ROI metrics.
- Resizable, collapsible, floating, and maximizable Plots dock.
- Persisted geometry, dock state, splitter sizes, last directory, layout, and
  analysis state through `QSettings`.

Multi View uses side-by-side for two items, a smart focus layout for three, 2×2
for four, and 3×2 for five/six. A seventh derived Difference result is displayed
in Single View when all six source slots are occupied.

RAW always opens a confirmation dialog. Same-name JSON sidecars pre-fill the
profile. Profile `name` remains serialized metadata but is not editable. The
same RAW path may be reloaded with corrected settings.

## Future product scope

The complete product adds packed Bayer decoding, demosaic, alpha overlay,
persistent sessions and ROI management, remote GPU IQA/image evaluation,
heatmap overlays, and a validated standalone Windows distribution. Remote
results include scalar and attribute scores, pixel maps, model/preprocessing
versions, and inference metadata.
