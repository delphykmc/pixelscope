# Image View

<!-- pixelscope:screenshot window-overview -->

Image View is the primary visual inspection surface.

<!-- pixelscope:screenshot single-image -->

## Single and Multi View

**Single View** (`Ctrl+1`) focuses on one source in the current page context. **Multi View** (`Ctrl+2`) presents the Current Comparison Page, up to six sources. Number keys `1` through `6` activate the corresponding visible page-local slot.

Press **T** to move the last real source on the Current Comparison Page to **Primary**, shifting the other displayed source positions forward. Repeated presses cycle through the sources in Single and Multi View; Difference and split-derived tiles are not part of this rotation. This does not reorder Files selection.

Use **Left/Right** to move through the complete ordered Selected set. Crossing a six-image boundary moves to the page that contains the new active source; `PageUp/PageDown` remain reserved for Folder Position movement instead.

## Zoom, pan, and inspection

Use the viewer controls and pointer interactions to inspect source detail. Shared comparison coordinates support synchronized cursor, ROI, and Line Profile workflows where the participating source geometry allows it.

**Fit** frames the image in the available tile; it is not a 100% scale.
**100% (1:1)** means one source *reference* pixel spans one physical monitor pixel, with the active screen's device-pixel ratio taken into account. 200% and 400% span two and four physical pixels per reference pixel respectively. The tile zoom label is measured from the displayed image's transform, not the requested command. A nonuniform, mirrored, rotated, or sheared image mapping has no trustworthy single zoom percentage and is shown as unavailable. Small images may have empty canvas around them at 100%; they are not enlarged to fill the tile. Bayer and subsampled YUV views retain their reference-grid coordinate scale.

On synchronized Multi View tiles, zoom/pan uses a common reference-space center and physical scale even when tile sizes differ. With synchronization disabled, the tiles can keep independent centers. On Windows, check the actual physical zoom after a monitor/DPI change if the OS or remote desktop changes its scale reporting.

## Display gain

Display gain changes presentation only; it does not rewrite native source values used by Statistics or Difference.

- `[` / `]`: decrease/increase all visible display gains by 0.5 EV.
- `\`: reset display gains.
- Single View: `Alt+[` / `Alt+]` adjust the selected Before pane, and `Shift+[` / `Shift+]` adjust the selected After pane.
- Multi View: `Alt+[` / `Alt+]` adjust the active slot.

## Split channels

`S` toggles the Split-channel action when it is applicable. Available split/channel views depend on the source family; do not interpret a display transform as a change to native numeric analysis.

## Pick is separate from activation

In Multi View, **Pick** marks a source for temporary curation. Activating a tile, panning, drawing an ROI, or drawing a Line Profile does not itself change Pick membership. See [Curate a large selection](../workflows/curate-selection.md).

## Related topics

See [ROI](../workflows/inspect-roi.md), [Line Profile](line-profile.md), and [Difference](difference.md).
