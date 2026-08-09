# PixelScope user guide

## Register, select, and view images

PixelScope distinguishes five states:

- **Registered**: the image is known to the Files workspace.
- **Selected**: the image is in the ordered logical comparison set.
- **Current Comparison Page**: the current working subset of Selected, maximum six.
- **Presented**: the current viewer representation of that page.
- **Resident**: the decoded native source is currently retained in memory when
  required.

The six-image limit belongs to the **Current Comparison Page**, not Files
registration or logical Selected membership. You may register many folders/images
and select more than six; PixelScope works on them in six-image Comparison Pages.

`Analysis Working Set = Current Comparison Page`.
Viewer slot numbers are always local `1..6` inside that page.

### Open Images...

Use **File > Open Images...** (`Ctrl+O`) when you are choosing image files to look
at now. The dialog supports multiple files and exactly these formats:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

All supported selected files are registered and become the current ordered
Selected set. If 15 files are supplied, all 15 remain Selected. The initial
Comparison Page is images 1–6, followed by 7–12 and 13–15.

PNG/BMP/JPEG open directly. RAW uses the same command but resolves RAW profile
metadata internally. There is no separate top-level RAW-open command.

### Open Folders...

Use **File > Open Folders...** (`Ctrl+Shift+O`) when you are adding datasets to the
Files workspace. The Qt dialog supports multiple existing directories in one
operation. Duplicate resolved paths are removed deterministically and folder count
is not limited to six.

Opening folders is **registration-only**:

- supported images are added to Files;
- the current Selected set does not change;
- the Current Comparison Page does not change;
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

- direct image files → register and make them the Selected set;
- folders → register their supported contents only;
- mixed image files + folders → direct files become Selected while folder contents
  are registered only.

Dropping one, two, six, or more folders behaves the same way. There is no special
two-folder auto-comparison behavior. Unsupported files and standalone `.json`
files are ignored rather than interpreted as RAW.

## Current Comparison Page navigation

When six or fewer images are Selected, there is one Comparison Page and the
large-selection controls stay hidden. Existing Auto/Single/Multi behavior is
unchanged.

When more than six images are Selected, the toolbar shows the current range, for
example:

```text
[‹] 7–12 of 15 [›]
```

- **Ctrl+Left**: Previous Comparison Page.
- **Ctrl+Right**: Next Comparison Page.
- Page navigation does not wrap at the first/last page.
- Changing page does not change Selected membership/order.
- The active local slot is preserved when possible; a short final page clamps to
  its last available slot.

In Multi View, large selections keep a six-slot grid for continuity. A final
three-image page occupies slots 1–3 and leaves slots 4–6 empty rather than changing
geometry.

In Single View, one image is presented but its page context is still the full
Current Comparison Page. Number keys **1–6** always mean local page slots.
For example, image10 on the 7–12 page is slot **4**, not slot 10.

## Fine image navigation

**Left/Right** remains Previous/Next Selected Image across the complete ordered
Selected set.

If Single View is showing image12, pressing Right moves to image13 and automatically
changes the Current Comparison Page from 7–12 to 13–15. image13 is then local slot
1. The reverse occurs when moving Left across the boundary.

Up/Down remains Files-tree row navigation.

## Folder Position navigation

PageDown/PageUp remains exclusively Folder Position navigation; it is not reused
for Comparison Page paging.

Folder Position requires one to six Selected files from distinct folders. If 20
folders are registered but the comparison contains A005, D005, F005, and K005,
PageDown targets A006, D006, F006, and K006 only. All members move atomically in
natural filename order. If any participating folder is at an endpoint, selection
is unchanged and the status bar reports the boundary.

When **more than six images are Selected**, Folder Position is unavailable and
PageUp/PageDown does not partially move only the current page. Reduce Selected to
one-to-six images to use Folder Position again.

## View and navigate

- **Auto** chooses the current layout from the applicable comparison size.
- **Single View** presents one active image from the Current Comparison Page.
- **Multi View** presents the Current Comparison Page with at most six source tiles.
- Keys 1–6 and Single View header navigation address page-local slots.
- Two-, four-, and six-image layouts keep equal tile sizes. Three- and five-image
  layouts enlarge the primary tile for `Selected <= 6`.
- For `Selected > 6`, Multi View keeps six-slot geometry even on a partial final
  page.
- Selecting a primary flag changes presentation order within the Current Comparison
  Page without changing Selected ordering or page membership.
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

ROI normalization, Statistics, Histogram, and Line Profile all use the Current
Comparison Page as the default analysis working set.

## Statistics and Histogram

Statistics supports Full image and Active ROI scopes. The Images summary reports
bit depth and analyzed pixel count. RGB/RGBA uses R/G/B for analysis; RGBA alpha
is ignored. Bayer uses R/Gr/Gb/B native mosaic planes.

Histogram supports Auto/256/1024/4096 bins, Count/Normalized/Log count, Separate or
Overlay display, and native code-value x ranges. Identical source/generation/ROI/
bin requests do not restart unchanged numerical work.

When you change Comparison Page, Statistics and Histogram move to that same page;
they do not remain bound to the first six Selected images.

## Line Profile

Line Profile supports Overlay, Separate by image, and Separate by channel. In
Difference-from-reference mode, reference priority is primary, then active, then
first displayed, while an explicitly selected available reference remains stable.
Its normal source set follows the Current Comparison Page.

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
Selected/current-page lifecycle.

Difference's available/default inputs follow the Current Comparison Page, while an
explicit Image 1/Image 2 pair remains owned by the Difference feature.

When all six source slots of a Comparison Page are occupied, the derived Difference
result is presented in Single View until disabled, preserving the existing
six-source Difference workspace contract.

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
RAW Profile dialogs or decoding every source.

A RAW may also be logically Selected while it is outside the Current Comparison
Page. In that state it does not prompt, decode, or require residency merely because
it is Selected. Profile resolution occurs when the RAW enters the foreground
Current Comparison Page and native source is required.

Within one foreground presentation attempt, an unresolved RAW dialog appears at
most once. Cancel keeps the RAW registered/pending, starts no worker, and passive
rerenders do not immediately reopen it. A later explicit foreground action may
retry.

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
The default is 256 MiB. Current Comparison Page sources and other correctness
requirements are protected; a large Selected set does **not** automatically protect
every visited off-page source. Off-page Selected source may be evicted under the P2
soft budget and normally reload when its page is revisited.

**Difference Map Cache** is separate, default 128 MiB. Source eviction does not by
itself discard a valid generation-keyed Difference map.

**Preload Next Folder Position** remains exactly one valid one-to-six Selected
Folder Position ahead, direction +1, on a separate max-one worker. It does not
preload the next Comparison Page. A physically RUNNING matching Folder Position
preload may transfer to foreground authority without duplicate decode. Unresolved
RAW without a profile is skipped rather than prompting from speculative preload.

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
