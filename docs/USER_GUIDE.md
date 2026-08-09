# PixelScope user guide

## Register and select images

Use **Open Images**, **Open Folder**, **Open RAW with Profile**, or drag
files/folders into the application. Files are grouped by parent folder.
Ctrl/Shift selection forms the ordered comparison set; up to six source images
can be visible.

When one to six files are selected from distinct participating folders, Page
Down/Page Up moves every folder atomically in natural filename order. Navigation
uses files already registered in PixelScope; it does not discover or register
new siblings. The shortcuts work while the Files view or a visible image tile
has focus. If any folder reaches an endpoint, no folder changes and the status
bar reports the boundary.

## View and navigate

- **Auto** chooses Single or Multi View from the selection.
- **Single View** shows the active image. Use **Previous/Next Selected Image**
  (Left/Right), keys 1–6, or header navigation without changing selection
  membership, zoom, or offset.
- Up/Down remains the Files tree's previous/next row navigation. PageUp/PageDown
  performs Previous/Next Folder Position navigation.
- **Multi View** uses fixed layouts for two through six images.
- Every regular Multi View containing two through six images shows a primary
  flag. The first displayed image is the implicit primary until another flag is
  selected.
- Selecting a primary flag moves that image to the first tile without changing
  Files selection order or image IDs.
- Two-, four-, and six-image layouts keep equal tile sizes. Three- and
  five-image layouts enlarge the first, primary tile.
- Split Channels component tiles do not show primary flags because their
  R/G/B or Bayer order is fixed.
- **Fit** fits visible tiles; **100%** uses native pixel scale.
- **Split Channels** shows RGB or Bayer channel views and retains its checked
  state while another supported image loads.
- **Display Gain** provides 1×, 2×, 4×, 8×, and 16× viewer-only digital gain for
  ordinary Gray/RGB/RGBA and RAW presentations. One session-local gain is shared
  by supported Single/Multi View tiles. With focus inside the image viewer, press
  **+** to move one gain step higher and **-** to move one step lower. The
  shortcuts stay at 1×/16× at the minimum/maximum. With focus in the Files tree,
  **+**/**-** keep their native folder expand/collapse behavior and do not change
  Display Gain.

For ordinary images, Gray and RGB use zero-anchored gain (`gain × source`). The
same gain is applied to R/G/B, so Display Gain does not introduce a color-balance
adjustment. RGBA applies gain to RGB only; transparency/alpha remains exactly the
document's canonical 1× preview alpha. Ordinary RGB Split Channels use the same
zero-anchored gain while retaining their colored channel presentation.

At **1×**, PixelScope reuses the canonical document preview directly. Gain above
1× is generated from the already resident native source as a viewer-local derived
preview. Returning to 1× restores the canonical preview. Hidden/replaced gained
tiles release their derived preview and regenerate the current session gain if
shown again.

Display Gain does not change pixel readout, Statistics, Histogram, Line Profile,
Split Channel native data, Difference, or source residency. Difference has its
own independent presentation Gain and does not receive Display Gain a second time.

## Cursor, ROI, and line selection

Moving over an image synchronizes the crosshair. The status bar shows position
and the value under the active pointer.

- Ctrl+drag creates one shared rectangular ROI; double-click or Esc clears it.
- Shift+drag creates a horizontal or vertical line from the longer gesture axis.
- Shift+Esc clears the shared line.

Alt+drag does not create a Line Profile. The Edit menu names the clear operations
**Clear ROI** and **Clear Line Profile**. Esc never changes the shared line, and
Shift+Esc never changes the ROI.

## Statistics and Histogram

Statistics can target active, selected, or visible images and Full image or
Active ROI. The panel follows the RAW dialog hierarchy with separate Region,
Images, and Channel statistics groups. Region shows aligned Scope and Bounds
rows, using full `x`, `y`, `width`, and `height` labels. Active ROI remains
disabled until a shared ROI exists and returns to Full image when that ROI is
cleared. The Images summary reports each image's bit depth and analyzed Pixels
so channel statistics can be interpreted in the correct code range. Long image
labels stay on one row and are middle-elided when the Analysis sidebar is
narrow; the complete source metadata remains available in the tooltip. Thin row
separators mark the start of each image group in Channel statistics.

Analysis activity appears below the statistics table only while work is pending
or when a status/error message must be shown. The activity area collapses after
a successful calculation so it does not leave permanent empty space.

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
The initial reference is the primary image, then the active image, then the
first displayed image. The selected reference remains stable while that
document is available and is rendered as exact zero.

## Difference

Choose Image 1 and Image 2 in **Analysis > Difference**, then calculate.
PixelScope compares only compatible image families: Gray with Gray, RGB/RGBA with
RGB/RGBA, or Bayer with Bayer when the CFA pattern matches. RGBA alpha is ignored.
Gray exposes only **Gray**; RGB/RGBA exposes **All / R / G / B**; Bayer exposes
**Mosaic / R / Gr / Gb / B**. Cross-family, size-mismatch, and CFA-mismatch pairs
are rejected; PixelScope does not silently convert RGB to grayscale.

The panel shows compact **Scope** and **Domain** fields. Equal effective bit depths
use **Native** code values. Different effective bit depths use **Normalized
[0–1]**: each source is divided by its own effective full-scale code value before
Difference is calculated. This is source full-scale normalization; RAW black/white
levels, Display Gain, previews, and demosaic do not change it.

Absolute and Mask displays derive from the cached map, and reversed pairs reuse
the same order-independent cache entry. The Threshold unit follows the domain:
**code** for Native or **%FS** for Normalized. In normalized mode, `1.00 %FS` is
`0.01` in the `[0,1]` domain. Mask comparison is strict `>`, so a pixel exactly at
the threshold is not masked. Difference-panel Gain retains the existing Absolute
Difference presentation behavior and is independent from toolbar Display Gain.
Full image/Active ROI controls metrics.

The persisted **Settings > Difference Defaults > Threshold** remains the Native
code threshold under settings schema v5. Normalized Threshold is separate, starts
at **1.00 %FS**, and is remembered only for the current application session.
Switching between native and normalized pairs keeps the most recent threshold for
each domain during that session. Validation uses short visible labels such as
**Layout mismatch**, **Size mismatch**, or **CFA mismatch**; hover the status or
Calculate control for the detailed reason.

With six selected sources, Difference opens in Single View until disabled.

## Settings

Open **Edit > Settings...**. The left side selects **General**, **Files**, or
**Performance** and the right side shows that category's options.

Display Gain is not an application setting and is distinct from Difference Gain.
It is a viewer-only session control and returns to 1× on a new PixelScope session.

### General

**Don't Show RAW JSON Profiles** controls repeated confirmation for valid RAW
JSON sidecars. This persistent preference lives in Settings; it is not duplicated
in the File menu. Choosing the equivalent don't-show-again option from the RAW
confirmation dialog updates only this setting and preserves the other Settings
values.

**Require Exact RAW File Size** controls RAW byte-count validation. When off,
PixelScope accepts files that contain at least the bytes required by the selected
profile, so trailing bytes are allowed. Undersized files are always rejected.
When on, the file size must exactly match the profile requirement. The same
policy is used when deciding whether a JSON sidecar may bypass the RAW profile
confirmation dialog.

Under **Difference Defaults**, **Threshold** sets the initial native code-domain
Difference mask threshold and **Gain** sets the initial Absolute Difference
amplification. Persisted values initialize the Difference panel on startup. Saving
either value from Settings updates the current panel immediately and does not
require restart. The mixed-bit normalized `%FS` threshold is intentionally
session-local and is not a separate persisted setting in schema v5.

### Files

**Default Open Folder** controls the starting location for Open Images, Open
Folder, and Open RAW dialogs. **Default Export Folder** controls the starting
location for export dialogs.

Both fields are optional. Leave a field blank to keep PixelScope's existing
last-used-folder behavior. Setting a folder does not lock you to that folder; it
only chooses where the dialog starts. If a configured folder is unavailable,
PixelScope falls back to the remembered last-used folder. File-location changes
apply immediately and do not require restart.

### Performance

**Decoded Source Memory** is the budget for native decoded source image arrays
kept resident for fast navigation. The default is 256 MiB, the allowed range is
128–2560 MiB, and the control moves in 128 MiB steps. The default targets about
eight typical UHD working images with headroom; actual capacity varies with
resolution, dtype, and channel count. The green residency indicator in Files
means that source's native decoded array is currently resident; it does not mean
total application memory or a Difference cache entry.

PixelScope releases the least-recently-used unprotected sources when their bytes
exceed this budget. Visible, selected, active/analysis, current Difference-pair,
and currently loading sources are protected. The budget is therefore soft: a
required image, including one larger than the whole budget, remains available
while protected. Selecting a released source reloads it through the normal image
load path.

**Difference Map Cache** is the separate memory budget for calculated Difference
maps. Its default is 128 MiB, allowed range is 64–1280 MiB, and the control moves
in 64 MiB steps. Releasing a source for Decoded Source Memory does not by itself
discard a valid Difference map.

Both memory budgets are startup settings. Changing either saves the preference
but does not resize the current runtime owner. When an editable value differs
from its current startup value, the dialog shows **Changes take effect after
restarting PixelScope.** Returning both values to their current runtime settings
clears that indication.

When physical RAM is detected, the combined Source and Difference budgets may be
at most 50% of it. If Save detects a higher total, PixelScope warns, preserves
both entered values, and leaves Settings open so either value can be reduced. If
RAM detection is unavailable, product bounds alone apply. The machine-aware
limit is a conservative configuration guard, not a guarantee against OOM:
previews, Qt textures, worker temporaries, Python/Qt overhead, and protected
soft-budget overage are outside these two counters.

**Preload Next Folder Position** decodes exactly one registered Folder Position
ahead after normal image loading becomes idle. It is enabled by default. Preload
uses a separate single-worker queue and never makes interactive loading wait.
Already resident targets are reused, previous and next-next positions are not
decoded, and no filesystem siblings are discovered automatically.

If you navigate forward while the exact required image is still RUNNING in that
preload worker, PixelScope reuses the same decode as foreground work instead of
cancelling it just to start the same image again. This reuse does not add another
worker, increase preload depth, or change direction: preload remains exactly one
Folder Position ahead with one preload worker. For a multi-folder position, the
one matching RUNNING preload member may be reused while the other required
members load normally.

Preloaded sources use the ordinary Decoded Source Memory budget and have no
special protection after speculative completion, so low-budget pressure may
release them before navigation. A promoted running preload becomes protected as
foreground-required work. Cancellation is advisory; PixelScope validates plan,
document generation, path/RAW profile, exact RAW-size policy, and normal-load
authority before keeping a result. A speculative failure shows no modal error
and the normal load still retries when you navigate to that position. Once a
running preload has been promoted because you actually navigated to it, a failure
uses the same foreground error/status behavior as a normal image load. Preload
enablement is startup-only and participates in the same restart-required
indication as both memory budgets.

**Reset Settings** restores only application preferences to their defaults. It
does not reset window layout, dock/splitter geometry, remembered last directory,
or other workspace/session state. Use **View > Reset Workspace Layout** for
layout state instead.

Docking and layout defaults are intentionally not duplicated in Settings because
PixelScope already restores the exact saved workspace.

## Runtime Diagnostics

PixelScope provides deterministic, inexpensive, sanitized runtime observability
for automated validation, final P2 characterization, and support troubleshooting.
The only end-user surface is **Help > Copy Diagnostics**.

Choose **Help > Copy Diagnostics** when support or development asks for runtime
context. PixelScope takes one current bounded snapshot, formats the canonical
sanitized text, copies that exact text to the clipboard, and briefly shows
**Diagnostics copied to clipboard** in the status bar. There is no diagnostics
window, live monitor, Refresh control, timer, or diagnostics text-file export.

The copied text reports Decoded Source residency, Difference Map Cache usage,
foreground and preload worker counts, preload counters including
**Promoted to foreground**, stale results, and up to ten recent accepted
foreground/preload failures. A promoted physical preload worker is reported as
foreground work rather than being double-counted as both foreground and preload.
Obsolete cancelled or replanned speculative preload failures are not promoted
into recent failure history.

Diagnostics omit registered source paths and image content. Failure messages
redact absolute Windows/POSIX paths, credential-like assignments including
multi-word values, bearer tokens, URL detail, traceback context, and excess
length. Copying diagnostics does not start image/preload work, calculate
Difference, alter cache LRU order, scan files, cancel workers, refresh preload,
or change selection/rendering. Unchanged runtime state produces identical,
timestamp-free text.

Automated tests and final P2 characterization can consume
`MainWindow.runtime_diagnostics_snapshot()` directly; the support-copy action is
not required to access the diagnostics API.

## Plots dock

The title bar provides Float/Dock, Maximize/Restore, and Hide. The toolbar
**Plots** action shows a hidden dock. The last selected Histogram/Line Profile
tab is restored on restart through `analysis/bottom_tab`.

A floating Plots window remembers its independent position and size across
hide/show, re-docking, and restart. Double-click the floating title bar to
maximize or restore it; the explicit Maximize/Restore button uses the same
state transition.

## RAW

Opening RAW uses a validated profile. A same-name JSON sidecar pre-fills the
dialog. The **Don't Show RAW JSON Profiles** preference can accept those
profiles without repeated confirmation when the file-size policy also matches.
Reloading the same path is allowed.

Unpacked profiles specify `uint8` or `uint16`, effective bit depth, byte order,
and LSB/MSB alignment where applicable. Packed choices are MIPI RAW10, RAW12,
and RAW14; non-applicable container, byte-order, and alignment rows are hidden.
The profile also retains Black Level and White Level metadata; Bayer profiles may
carry independent R/Gr/Gb/B Black Levels.

Decoded RAW samples are the authoritative native values. Pixel readout,
Statistics, Histogram, Line Profile, Split Channels, and Difference continue to
use those native values even when Display Gain changes.

At **Display Gain = 1×**, the viewer maps the full effective native code range to
the preview: RAW10 uses 0–1023, RAW12 uses 0–4095, and RAW14 uses 0–16383. Black
Level is not subtracted from this 1× display and White Level is not treated as the
display maximum.

For gain above 1×, PixelScope keeps Black Level stationary and magnifies the
residual around it:

```text
gained = black + gain * (native - black)
```

For Bayer RAW, each R/Gr/Gb/B Black Level is used at the matching CFA position.
Values below black and above full scale are preserved through the gain arithmetic
and clipped only when the final 8-bit preview is produced. This is presentation
only; it does not alter the stored source samples or analysis results.

Display Gain is session-local and starts at **1×** for a new application session.
It is not stored in the RAW profile or Settings. White Level remains profile
metadata for possible future explicit processing and is not used by the current
native or gained display mapping. With focus inside the image-presentation area,
the **+** and **-** shortcuts step through the same discrete gain values and remain
synchronized with the toolbar selector. With focus in the Files tree, those keys
retain Qt-native folder expand/collapse behavior instead of changing gain.

Grayscale and Bayer mosaics are supported. Bayer remains native mosaic/channel
inspection; no demosaic, white balance, CCM, or tone-mapped RAW preview is
provided by the current RAW display contract.

Production constraints are CPython 3.10 x64, PySide6 6.4.2, and a future
PyInstaller 5.7 `onedir` build.
