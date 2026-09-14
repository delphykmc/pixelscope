# Image View

Image View is the primary visual inspection surface.

## Single and Multi View

**Single View** (`Ctrl+1`) focuses on one source. **Multi View** (`Ctrl+2`) presents the Current Comparison Page, up to six sources. Number keys `1` through `6` activate the corresponding visible slot.

## Zoom, pan, and inspection

Use the viewer controls and pointer interactions to inspect source detail. Shared comparison coordinates support synchronized ROI and Line Profile workflows where the participating source geometry allows it.

## Display gain

Display gain changes presentation only; it does not rewrite native source values used by Statistics or Difference.

- `[` / `]`: decrease/increase all visible display gains by 0.5 EV.
- `\`: reset display gains.
- Single View: `Alt+[` / `Alt+]` adjust the selected Before pane, and `Shift+[` / `Shift+]` adjust the selected After pane.
- Multi View: `Alt+[` / `Alt+]` adjust the active slot.

## Split channels

`S` toggles the Split-channel action when it is applicable. Available split/channel views depend on the source family; do not interpret a display transform as a change to native numeric analysis.

## Related topics

See [ROI](../workflows/inspect-roi.md), [Line Profile](line-profile.md), and [Difference](difference.md).
