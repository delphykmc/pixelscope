# PixelScope user guide

## Register and select images

Use **Open Images**, **Open Folder**, **Open RAW**, or drag files/folders into
the application. Files are grouped by parent folder. Ctrl/Shift selection forms
the ordered comparison set; up to six source images can be visible.

When one file is selected from each of several folders, **Page Down** and
**Page Up** advance or rewind every folder atomically in natural filename order.
If any folder reaches its endpoint, no folder changes.

## View and navigate

- **Auto** chooses Single or Multi View from the selection.
- **Single View** shows the active image. Use Left/Right, keys 1–6, or header
  buttons to toggle selected images without changing zoom or offset.
- **Multi View** chooses side-by-side, smart three-image, 2×2, or 3×2 layout.
- The upward tile control promotes that image to the first raster position.
  Other images shift right while logical ID badges remain unchanged.
- **Fit** fits all visible tiles; **100%** uses native pixel scale.

## Cursor, ROI, and line profile

Moving over an image synchronizes the crosshair. The structured status bar
shows Position and the value from the tile under the pointer.

- Ctrl+drag creates one shared rectangular ROI; double-click or Esc clears it.
- Alt+drag creates a horizontal or vertical line from the longer gesture axis.
  Line Profile displays every selected image and its RGB or Bayer subchannels.

## Statistics and histogram

Statistics can target active, selected, or visible images and Full image or
Active ROI. Each numeric row has explicit Id and Ch columns. Copy the table or
export CSV from the application.

Histogram supports Separate/Overlay, Count/Normalized, and native/0–1 ranges.
Bins follow effective bit depth. RGB uses R/G/B and Bayer uses R/Gr/Gb/B.

## Difference

Select at least two images, choose Image 1 and Image 2 in **Analysis >
Difference**, and calculate. The first two distinct selected images are the
default pair. Reversed pairs share one order-independent cache.

Absolute and Mask displays derive from the cached native map. Gain and
Threshold change presentation only; Full image/Active ROI controls metrics.
With six selected sources, Diff opens in Single View and Multi View remains
unavailable until Diff is disabled.

## Plots dock

The title bar has three controls:

1. Float/Dock
2. Maximize/Restore
3. Hide Plots

A maximized dock restores to its original dock position. A maximized floating
window restores to its prior floating state. Use the toolbar **Plots** action
to show a hidden dock again.

## RAW

Opening RAW always presents profile confirmation. A same-name JSON sidecar
pre-fills controls; otherwise defaults are used. Profile `name` remains JSON
metadata but is not editable. Reloading the same RAW path is allowed so an
incorrect profile can be corrected.

Production constraints are CPython 3.10 x64, PySide6 6.4.2, and a future
PyInstaller 5.7 `onedir` build.
