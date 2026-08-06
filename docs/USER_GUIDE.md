# PixelScope user guide

## Register and select images

Use **Open Images**, **Open Folder**, **Open RAW with Profile**, or drag
files/folders into the application. Files are grouped by parent folder.
Ctrl/Shift selection forms the ordered comparison set; up to six source images
can be visible.

When one file is selected from each participating folder, Page Down/Page Up
moves every folder atomically in natural filename order. If any folder reaches
an endpoint, no folder changes.

## View and navigate

- **Auto** chooses Single or Multi View from the selection.
- **Single View** shows the active image. Use Left/Right, keys 1–6, or header
  navigation without changing zoom or offset.
- **Multi View** uses fixed layouts for two through six images.
- The focus control promotes an image in the three- and five-image layouts.
- **Fit** fits visible tiles; **100%** uses native pixel scale.
- **Split Channels** shows RGB or Bayer channel views and retains its checked
  state while another supported image loads.

## Cursor, ROI, and line selection

Moving over an image synchronizes the crosshair. The status bar shows position
and the value under the active pointer.

- Ctrl+drag creates one shared rectangular ROI; double-click or Esc clears it.
- Alt+drag creates a horizontal or vertical line from the longer gesture axis.
- Shift+Esc clears the shared line.

## Statistics and Histogram

Statistics can target active, selected, or visible images and Full image or
Active ROI. Rows have explicit image and channel fields; the summary reports
Pixels.

Histogram supports:

- Bins: Auto, 256, 1024, 4096
- Y mode: Count, Normalized, Log count
- Separate or Overlay display
- Native code-value x ranges

RGB uses R/G/B; Bayer uses R/Gr/Gb/B.

## Line Profile

Line Profile supports Overlay, Separate by image, and Separate by channel
views. Legends use compact image-ID/channel labels.

When Y mode is **Difference from reference**, a Reference selector appears.
The initial reference is focused/pinned, then active, then first displayed.
The selected reference remains stable while that document is available and is
rendered as exact zero.

## Difference

Choose Image 1 and Image 2 in **Analysis > Difference**, then calculate.
Reversed pairs share one native-map cache.

Absolute and Mask displays derive from the cached map. Gain and Threshold change
presentation; Full image/Active ROI controls metrics. With six selected sources,
Difference opens in Single View until disabled.

## Plots dock

The title bar provides Float/Dock, Maximize/Restore, and Hide. The toolbar
**Plots** action shows a hidden dock. The last selected Histogram/Line Profile
tab is restored on restart.

Independent floating-window geometry and title-bar double-click
maximize/restore are not yet implemented.

## RAW

Opening RAW uses a validated profile. A same-name JSON sidecar pre-fills the
dialog. The **Don't Show RAW JSON Profiles** preference can accept those
profiles without repeated confirmation. Reloading the same path is allowed.

Unpacked profiles specify `uint8` or `uint16`, effective bit depth, byte order,
and LSB/MSB alignment where applicable. Packed choices are MIPI RAW10, RAW12,
and RAW14; non-applicable container, byte-order, and alignment rows are hidden.

Grayscale and Bayer mosaics are supported. Bayer is displayed/analyzed as
native R/Gr/Gb/B planes; no demosaic preview is provided.

Production constraints are CPython 3.10 x64, PySide6 6.4.2, and a future
PyInstaller 5.7 `onedir` build.
