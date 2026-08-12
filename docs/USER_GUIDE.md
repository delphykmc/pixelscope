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

### Open Folder...

Use **File > Open Folder...** (`Ctrl+Shift+O`) when you are adding a dataset folder
to the Files workspace. The native folder picker selects one directory per
invocation. To register several folders at once, drag/drop them into Files; the same
registration API deduplicates supplied paths and has no six-folder limit.

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
Any captured temporary curation baseline and Pick Set are also unaffected because
Selected membership did not change.

If images are registered but nothing is selected, the center workspace shows
**Select an image from Files to view**. A truly empty workspace shows **Drop images
or folders here** with Open Images/Open Folder buttons.

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

The presentation-control row above the image workspace always shows Comparison
Page status, including when there is only one page. Previous/next arrows remain in
place and are disabled when that direction is unavailable, so the controls do not
shift as selection size changes. Existing Auto/Single/Multi behavior remains
unchanged for six or fewer Selected images. For example, a three-page selection may
show:

```text
Page [‹] 2 / 3 [›]  7–12 of 15
```

- **Ctrl+Left**: Previous Comparison Page when available.
- **Ctrl+Right**: Next Comparison Page when available.
- Page navigation does not wrap at the first/last page. At an unavailable endpoint
  the application shortcut is disabled, so Ctrl+Arrow remains available to the
  focused editor/control.
- Changing page does not change Selected membership/order.
- The active local slot is preserved when possible; a short final page clamps to
  its last available slot.

In Multi View, large selections keep a six-slot grid for continuity. A final
three-image page occupies slots 1–3 and leaves slots 4–6 empty rather than changing
geometry.

In Single View, one image is presented but its page context is still the full
Current Comparison Page. Number keys **1–6** always mean local page slots.
For example, image10 on the 7–12 page is slot **4**, not slot 10.

## Pick and Keep Selection

Use the direct **Pick** controls in Multi View when a large Selected set contains
images you want to inspect page by page and reduce to a smaller comparison subset.
There is no separate Review Select mode to enter.

Each eligible native source tile in Multi View shows **Pick**. Clicking Pick toggles
that source in the temporary Pick Set. The first checked Pick captures the current
ordered Selected set as the temporary baseline internally. The button text remains
**Pick** in both states; a picked tile shows the button depressed/checked and uses a
bright-yellow tile-wide border. Normal tile activation and the Primary flag retain
their existing meanings, so **Active**, **Primary**, and Pick membership remain
independent.

A typical 15-image curation can be performed as follows:

1. In Multi View, click **Pick** on desired images on page 1.
2. Move to pages 2 and 3 with the normal Comparison Page controls and continue
   picking. Earlier picks remain remembered even while off-page.
3. Check **Selected N** in the presentation row for the current temporary Pick Set
   count. This number is not the Files logical Selected count.
4. Use **Clear Selection** to clear only the temporary Pick Set if you want to start
   the curation choices again.
5. Use **Keep Selection** to replace logical Selected with the picked subset.

**Keep Selection** is disabled when nothing is picked, so a zero-pick curation
cannot silently replace Selected with an empty set.

Keep Selection preserves the original baseline Selected order, not the order in
which picks were made. For example, if baseline Selected is `A B C D E F G` and
you pick `G → B → E`, the new Selected set is `B E G`. All non-picked images remain
Registered in Files and can be selected again later.

There is no separate Cancel command. **Clear Selection** removes the current Pick
membership without changing logical Selected. If another selection-oriented
workflow actually changes Selected—such as Open Images, direct image-file drag/drop,
Files selection replacement/removal, or Folder Position movement—the captured
baseline/Pick Set is invalidated before or with the normal selection operation.
Registration-only folder input does not cause this reset because it does not change
Selected. Temporary Pick state is not persisted across application restart.

Picks refer to the native registered source image. Split Channel items and derived
Difference presentation are not independent pick identities. Picking an image also
does not decode or preload off-page images, protect them in source residency, run
Difference or analysis, or otherwise change the Current Comparison Page working-set
authority.

Only the explicit **Pick** control changes curation membership. Normal image pan,
Ctrl+drag ROI, Shift+drag Line Profile, and ordinary tile activation do not toggle
Pick state.

## Save and open Comparison Sets

Use **File > Save Comparison Set...** to save the current logical comparison
membership for later reuse. PixelScope writes a `.pixelscope` JSON v1 artifact.

A Comparison Set stores:

- the ordered logical **Selected** native-source paths;
- the selected **Active** source when applicable;
- the current-page **Primary** source when applicable;
- the stable layout mode;
- resolved RAW profile metadata only when it is needed to reconstruct a saved RAW
  source.

Temporary Picks are not saved as their own membership. If you have checked Picks
but have **not** used Keep Selection, Save Comparison Set still writes the current
logical Selected set. If you first use **Keep Selection**, the resulting curated
Selected subset is what is saved. Saving never applies or clears Picks.

Use **File > Open Comparison Set...** to open a saved set. PixelScope validates the
artifact before replacing logical Selected. Loadable saved sources become Selected
in saved order; unrelated images already Registered in Files stay Registered. Saved
Active determines the resulting Current Comparison Page, then an applicable Primary
and the saved layout are restored. The Current Comparison Page/page offset itself is
not stored in the file.

If some saved paths are missing, the available sources are opened and a compact
warning reports the unavailable paths. If none of the saved sources can be loaded,
the current logical workspace is left unchanged. Corrupt files, unsupported/future
schema versions, wrong artifact kind, invalid paths/layout, or invalid embedded RAW
metadata are rejected without beginning registration or foreground loading.

Resolved RAW metadata saved in the artifact is restored before foreground use.
Unresolved RAW remains unresolved and follows the normal foreground RAW Profile
workflow when it is actually needed. Saving a Comparison Set does not force an
unresolved RAW to resolve.

Comparison Set v1 identifies sources by normalized **absolute local paths** and does
not relocate or fuzzy-match moved files. This makes the file deterministic but not
portable across arbitrary machines or directory layouts. A `.pixelscope` file can
also reveal local filesystem path names, so review it before sharing outside the
intended environment.

Comparison Sets do not save decoded image arrays, residency/LRU/preload state,
Difference maps/cache, Display Gain, analysis request/results, workers/tokens,
Split/Difference derived documents, transient zoom/pan, ROI/Line state, or temporary
Pick state. Application Settings schema remains version 5.

## Recent Entries

Use **File > Recent** to reopen recently used user entry paths. The menu is split
into explicit typed submenus:

- **Images** — successful direct image-open paths;
- **Folders** — successful folder-registration paths;
- **Comparison Sets** — successfully saved/opened `.pixelscope` artifact paths;
- **Clear Recent Entries** — clears all three recent-history lists.

Each type retains at most ten entries in most-recently-used order. Recent Image uses
the same selection-oriented behavior as Open Images. Recent Folder uses the same
registration-only behavior as Open Folder. Recent Comparison Set uses the same P4-B
loader and does not restore state independently.

Recent history is updated only after meaningful successful use. An Image moves to
the top after at least one image successfully opens. A Folder moves to the top after
successful folder registration, even when the existing folder currently contains no
supported images. A Comparison Set moves to the top only when at least one saved
source is actually loaded. A successful Comparison Set save enters Recent only after
the atomic save completes.

If a Recent path no longer exists, PixelScope asks whether to **Remove** or **Keep**
it. Remove deletes only that typed history entry; Keep leaves it unchanged. Neither
choice changes the current workspace. Existing-but-unusable resources are kept so
they can be retried later.

If a stored Recent type no longer matches the filesystem object—for example an Image
entry path is now a directory, or a Folder entry path is now a regular file—PixelScope
keeps the entry and reports that it is no longer the expected type. It does not
reinterpret the path as a different Open intent and does not promote it in MRU.

Missing sources *inside* a valid Comparison Set are different from a missing Recent
artifact. When some referenced sources are missing, P4-B opens the available subset
in saved order, shows its normal partial-missing warning, and the Comparison Set moves
to the Recent MRU top because it meaningfully opened. If none of the referenced
sources are loadable, the current workspace remains unchanged and the Recent entry
keeps its existing position. Corrupt/invalid existing `.pixelscope` artifacts also
stay in Recent so they can be fixed or retried.

Recent history stores normalized absolute local paths in QSettings. These paths can
reveal local filesystem names. **Clear Recent Entries** is the explicit removal and
privacy control. Recent history is separate from Application Settings schema v5;
**Reset Settings** does not clear it.

Recent bookkeeping is best-effort. A Recent-storage or menu-refresh failure does not
turn an otherwise successful image/folder/Comparison-Set operation into a failed
operation and does not own source residency, preload, analysis, Difference, Display
Gain, Current Comparison Page, or Pick state.

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

If Folder Position changes Selected after a curation baseline has been captured,
the temporary baseline/Pick Set is discarded before normal Folder Position
selection replacement.

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
- **Split Channels** keeps one source Selected in Files but derives transient
  R/G/B or R/Gr/Gb/B viewer-local subchannels. Multi View exposes explicit Primary;
  Single View navigates the same local subchannels with number/header/Left/Right
  controls. Native Statistics/Histogram/Line/Difference authority remains on the
  original source page.

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
data, Difference, source generation, or source residency. Pick identity also
remains the native source document ID, not a gained preview representation.
Comparison Sets do not persist Display Gain.

## Cursor, ROI, and Line Profile selection

Moving over an image synchronizes the crosshair and status readout.

- Ctrl+drag creates one shared ROI; Esc clears ROI.
- Shift+drag creates a horizontal or vertical Line Profile selection.
- Shift+Esc clears the shared line.
- Alt+drag does not create a Line Profile.

ROI normalization, Statistics, Histogram, and Line Profile all use the Current
Comparison Page as the default analysis working set. Temporary Pick Set does not
extend or replace that analysis working set.

## Statistics and Histogram

Statistics supports Full image and Active ROI scopes. The Images summary reports
bit depth and analyzed pixel count. RGB/RGBA uses R/G/B for analysis; RGBA alpha
is ignored. Bayer uses R/Gr/Gb/B native mosaic planes.

Histogram supports Auto/256/1024/4096 bins, Count/Normalized/Log count, Separate or
Overlay display, and native code-value x ranges. Identical source/generation/ROI/
bin requests do not restart unchanged numerical work.

When you change Comparison Page, Statistics and Histogram move to that same page;
they do not remain bound to the first six Selected images. Pick/Unpick alone does
not change their source set or reissue numerical analysis requests.

## Line Profile

Line Profile supports Overlay, Separate by image, and Separate by channel. In
Difference-from-reference mode, reference priority is primary, then active, then
first displayed, while an explicitly selected available reference remains stable.
Its normal source set follows the Current Comparison Page. Pick membership is not
a Line Profile input authority.

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
explicit Image 1/Image 2 pair remains owned by the Difference feature. Pick
membership does not change either authority and Pick/Unpick does not calculate or
invalidate Difference.

When all six source slots of a Comparison Page are occupied, the derived Difference
result is presented in Single View until disabled, preserving the existing
six-source Difference workspace contract. Returning to a page with a cached
Difference uses the same Diff-only Single View and restore behavior as a fresh
asynchronous result.

Comparison Sets do not persist Difference pair, map, cache, or Difference
presentation state.

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

A RAW may also be logically Selected or Picked while it is outside the Current
Comparison Page. In that state it does not prompt, decode, or require residency
merely because of Selected/Picked membership. Profile resolution occurs when the
RAW enters the foreground Current Comparison Page and native source is required.

Within one foreground presentation attempt, an unresolved RAW dialog appears at
most once. Cancel keeps the RAW registered/pending, starts no worker, and passive
rerenders do not immediately reopen it. A later explicit foreground action may
retry.

An unresolved RAW is not speculatively preloaded until a profile has been
resolved. PixelScope never guesses profile parameters merely to make folder
registration silent.

When opening a Comparison Set, saved resolved RAW profile metadata is restored
before foreground use. If the set contains an unresolved RAW without saved profile
metadata, it remains unresolved and uses this same foreground resolution path.

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
Folder. **Default Export Folder** controls export dialogs. Blank values retain
last-used-folder behavior. These are starting locations, not workspace registration
limits.

### Performance

**Decoded Source Memory** budgets native decoded `ImageDocument.source` arrays.
The default is 256 MiB. Current Comparison Page sources and other correctness
requirements are protected; a large Selected set does **not** automatically protect
every visited off-page source. Pick membership also does not protect an off-page
source. Off-page Selected/Picked source may be evicted under the P2 soft budget and
normally reload when its page is revisited. Saving or opening a Comparison Set does
not create Selected-wide residency protection.

**Difference Map Cache** is separate, default 128 MiB. Source eviction does not by
itself discard a valid generation-keyed Difference map.

**Preload Next Folder Position** remains exactly one valid one-to-six Selected
Folder Position ahead, direction +1, on a separate max-one worker. It does not
preload the next Comparison Page, Pick Set, Comparison Set, or Recent entry. A
physically RUNNING matching Folder Position preload may transfer to foreground
authority without duplicate decode. Unresolved RAW without a profile is skipped
rather than prompting from speculative preload.

Performance budget/preload changes are startup settings and display the restart-
required indication when they differ from current runtime values.

**Reset Settings** resets application preferences only. **View > Reset Workspace
Layout** resets workspace layout separately. The captured curation baseline/Pick Set
is temporary and adds no Settings/QSettings key. `.pixelscope` Comparison Sets are
separate external files and do not change Settings schema v5. Recent history uses
separate `recent/*` QSettings keys and is intentionally not cleared by Reset
Settings; use **File > Recent > Clear Recent Entries** instead.

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