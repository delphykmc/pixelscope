# PixelScope user guide

## Register, select, and view images

PixelScope distinguishes four states:

- **Registered**: the image is known to the Files workspace.
- **Selected**: the image is in the current comparison/analysis selection.
- **Presented**: the image currently occupies a viewer tile.
- **Resident**: the decoded native source is currently retained in memory.

The six-tile viewer limit applies to simultaneous presentation, not to Files
registration. You may register many folders/images while only a subset is selected
and at most the existing viewer-supported number is visible at once.

### Open Images...

Use **File > Open Images...** (`Ctrl+O`) when you are choosing image files to look
at now. The dialog supports multiple files and exactly these formats:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

All supported selected files are registered and become the current selection.
If more than six files are supplied, they are still registered/selected; Multi
View presents only the existing layout capacity rather than discarding files.

PNG/BMP/JPEG open directly. RAW uses the same command but resolves RAW profile
metadata internally. There is no separate top-level RAW-open command.

### Open Folders...

Use **File > Open Folders...** (`Ctrl+Shift+O`) when you are adding datasets to the
Files workspace. The Qt dialog supports multiple existing directories in one
operation. Duplicate resolved paths are removed deterministically and folder count
is not limited to six.

Opening folders is **registration-only**:

- supported images are added to Files;
- the current selection does not change;
- the current viewer/layout does not change;
- no first image is automatically selected;
- two folders do not implicitly create a comparison group;
- folders with no supported images are skipped while other folders continue.

Therefore adding folders while comparing A001/B001 leaves that comparison intact.
ROI, Line Profile, Difference presentation, Display Gain, active/primary state,
and current view state are not reset merely because another folder was registered.

If images are registered but nothing is selected, the center workspace shows
**Select an image from Files to view**. A truly empty workspace shows **Drop images
or folders here** with Open Images/Open Folders buttons.

### Drag and drop

Drag/drop follows the same intent rules:

- direct image files → register and select them for viewing;
- folders → register their supported contents only;
- mixed image files + folders → direct files become the selection while folder
  contents are registered only.

Dropping one, two, six, or more folders behaves the same way. There is no special
two-folder auto-comparison behavior. Unsupported files and standalone `.json`
files are ignored rather than interpreted as RAW.

## Folder Position navigation

PageDown/PageUp moves only the folders represented by the current selection. If 20
folders are registered but the current comparison contains A005, D005, F005, and
K005, PageDown targets A006, D006, F006, and K006 only.

Folder Position requires one to six selected files from distinct folders. All
members move atomically in natural filename order. If any participating folder is
at an endpoint, selection is unchanged and the status bar reports the boundary.

Up/Down remains Files-tree row navigation. Left/Right moves through the selected
image set.

## View and navigate

- **Auto** chooses the current layout from selection size.
- **Single View** presents one active selected image.
- **Multi View** uses fixed layouts with at most six simultaneous source tiles.
- Keys 1–6 and header navigation address the existing quick-navigation slots.
- Two-, four-, and six-image layouts keep equal tile sizes. Three- and five-image
  layouts enlarge the primary tile.
- Selecting a primary flag changes presentation order without changing Files
  selection membership.
- **Fit** fits visible tiles; **100%** uses native pixel scale.
- **Split Channels** presents RGB or Bayer component views.

Registration count is independent of all of these presentation choices.

## Display Gain

**Display Gain** provides 1×, 2×, 4×, 8×, and 16× viewer-only digital gain for
ordinary Gray/RGB/RGBA and RAW. One session-local value is shared by supported
Single/Multi View tiles.

With focus inside an image viewer, `+` moves one gain step higher and `-` lower.
With focus in Files, those keys keep Qt-native folder expand/collapse behavior.

- ordinary Gray/RGB uses zero-anchored gain (`gain × source`);
- ordinary RGB split channels use the same zero anchor;
- RGBA gains RGB only and preserves canonical 1× alpha;
- RAW uses its Black-derived gain anchor above 1×;
- Difference has its own independent presentation Gain.

At 1× PixelScope reuses canonical preview. Gain above 1× is generated from already
resident native source as viewer-local derived presentation. Display Gain does not
change pixel readout, Statistics, Histogram, Line Profile, Split Channel native
data, Difference, source generation, or source residency.

## Cursor, ROI, and Line Profile selection

Moving over an image synchronizes the crosshair and status readout.

- Ctrl+drag creates one shared ROI; Esc clears ROI.
- Shift+drag creates a horizontal or vertical Line Profile selection.
- Shift+Esc clears the shared line.
- Alt+drag does not create a Line Profile.

## Statistics and Histogram

Statistics supports Full image and Active ROI scopes. The Images summary reports
bit depth and analyzed pixel count. RGB/RGBA uses R/G/B for analysis; RGBA alpha
is ignored. Bayer uses R/Gr/Gb/B native mosaic planes.

Histogram supports Auto/256/1024/4096 bins, Count/Normalized/Log count, Separate or
Overlay display, and native code-value x ranges. Identical source/generation/ROI/
bin requests do not restart unchanged numerical work.

## Line Profile

Line Profile supports Overlay, Separate by image, and Separate by channel. In
Difference-from-reference mode, reference priority is primary, then active, then
first displayed, while an explicitly selected available reference remains stable.

## Difference

Difference supports:

- Gray ↔ Gray;
- RGB/RGBA ↔ RGB/RGBA, alpha ignored;
- Bayer ↔ Bayer with the same CFA pattern.

Cross-family, dimension-mismatch, CFA-mismatch, and unsupported layouts are
rejected. PixelScope does not silently convert RGB to grayscale.

Equal effective bit depths use the Native code domain. Mixed effective bit depths
normalize each source independently by its own effective full-scale code and use
float32 `[0,1]` Difference. RAW Black/White metadata, Display Gain, preview values,
and demosaic do not participate in this normalization.

Threshold units are `code` in Native and `%FS` in Normalized. Mask comparison is
strict `>`. Difference cache is order-independent and separate from decoded-source
residency. Folder-only registration does not invalidate a valid Difference cache
entry or clear the current Difference presentation because it does not alter the
selection/presentation lifecycle.

With six selected source images, the derived Difference result is presented in
Single View until disabled.

## RAW profile resolution

RAW uses the same **Open Images...** entry as ordinary images.

### Direct RAW file open/drop

- Exact same-basename sidecar (`frame.raw` + `frame.json`) is parsed and validated.
- With no sidecar, the editable RAW Profile dialog opens.
- An invalid sidecar shows a warning and then editable fallback.
- Cancelling profile entry prevents that directly opened RAW from being registered.
- Multiple RAW files are resolved independently; PixelScope does not silently
  reuse the previous profile or select one from byte size alone.

The dialog uses **Load Profile...** and **Save Profile...** terminology. JSON
remains the compatible storage format.

### RAW inside an opened/dropped folder

Folder registration is intentionally lazy. RAW paths and deterministic
same-basename sidecar paths can be registered in Files without immediately opening
RAW Profile dialogs or decoding every source. When you later select a pending RAW
that needs foreground loading, PixelScope resolves/validates its profile before
starting decode.

An unresolved RAW is not speculatively preloaded until a profile has been
resolved. PixelScope never guesses profile parameters merely to make folder
registration silent.

### RAW profile fields

Profiles retain storage format, unpacked container, effective bit depth, byte
order/alignment, width/height, offset/stride, Gray/Bayer layout, Bayer pattern,
Black Level, and White Level. Packed MIPI RAW10/12/14 owns fixed packing rules.
The same RAW path may be re-resolved with corrected profile settings while keeping
its document identity/reload semantics.

Current PixelScope intentionally has no global Profile Library, favorites/profile
CRUD manager, fuzzy or size-only profile suggestion, sensor/Bayer inference, or
automatic Black/White estimation.

## RAW display

Decoded RAW source remains the native analysis authority.

At Display Gain 1×, RAW display maps effective native full scale
`0..((1 << bit_depth) - 1)`. Black is not subtracted and White is not used as
display maximum. Above 1×, gained display follows:

```text
B + G * (X - B)
```

Gray uses its scalar Black anchor. Bayer may use channel-specific R/Gr/Gb/B Black
anchors; split Bayer views use their named channel anchor. Bayer processing uses
CFA parity-plane views rather than a full-frame Black map. White Level remains
metadata only.

## Settings

Open **Edit > Settings...**. Categories are **General**, **Files**, and
**Performance**.

### General

- **Don't Show RAW JSON Profiles** may suppress repeated confirmation only for a
  valid compatible same-basename sidecar.
- **Require Exact RAW File Size** switches between minimum-required-byte and exact-
  byte validation.
- **Difference Defaults** owns persisted native Threshold/Gain defaults.

### Files

**Default Open Folder** controls the initial directory for Open Images and Open
Folders. **Default Export Folder** controls export dialogs. Blank values retain
last-used-folder behavior. These are starting locations, not workspace registration
limits.

### Performance

**Decoded Source Memory** budgets native decoded `ImageDocument.source` arrays.
The default is 256 MiB. Required/visible/selected/active sources are protected and
the budget is soft.

**Difference Map Cache** is separate, default 128 MiB. Source eviction does not by
itself discard a valid generation-keyed Difference map.

**Preload Next Folder Position** remains exactly one selected Folder Position
ahead, direction +1, on a separate max-one worker. Preload is based on the current
selected comparison folders, not all registered folders. A physically RUNNING
matching preload may transfer to foreground authority without duplicate decode.
Unresolved RAW without a profile is skipped rather than prompting from speculative
preload.

Performance budget/preload changes are startup settings and display the restart-
required indication when they differ from current runtime values.

**Reset Settings** resets application preferences only. **View > Reset Workspace
Layout** resets workspace layout separately.

## Runtime Diagnostics

**Help > Copy Diagnostics** copies one deterministic sanitized snapshot. It reports
source residency, Difference cache usage, foreground/preload workers, preload
counters including promotion, stale results, and bounded recent accepted failures.

Diagnostics does not scan files, mutate selection, touch LRUs, start/cancel loads,
calculate Difference, or change presentation. Paths, credentials, traceback
context, and excess failure detail are sanitized.

## Plots dock

The Plots title bar provides Float/Dock, Maximize/Restore, and Hide. Histogram /
Line Profile selected tab and floating geometry are restored separately from
application Settings.
