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
- folders with no supported images are skipped while other inputs continue.

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

## Configure and submit Remote IQA

P5-C adds remote IQA submission to the existing IQA dock. The dock has three tabs:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

The remote workflow is separate from local Files/Selected analysis. Submitting a
batch does not register or decode the whole batch into the local image workspace.

### Configure Remote IQA

Open **Edit > Settings... > Remote IQA**.

Configure:

- **Server base URL** — the HTTP(S) endpoint for the external IQA service;
- one or more shared-storage mappings:
  - **Root ID** — a portable logical identifier understood by client and server;
  - **Client path** — the drive/UNC path for that root on this Windows machine;
- **Staging root** — optional logical root used when a submitted source is outside
  the configured shared roots.

The same logical root may have a different physical path on the server. For example:

```text
Root ID: iqadata
PixelScope client path: G:\IQA
server path: /home/data/IQA
```

PixelScope sends only the logical root plus relative path and integrity metadata.
The Windows client path is machine-local configuration; the server physical path is
not stored in PixelScope settings/result artifacts.

### Submit Current Pair

In the IQA **Setup** tab, Current Pair submits exactly two variants `A` and `B`.
They are the **underlying Current Comparison Page documents** when exactly two
eligible images are present.

Current Pair requires:

- exactly two eligible source images;
- PNG/JPG/JPEG/BMP input;
- matching original image dimensions.

Remote IQA currently does **not** accept RAW and PixelScope does not silently
demosaic/convert RAW for submission.

A/B submission identity does not change when you change:

- Primary;
- Active;
- tile/view order;
- Single/Multi View;
- Display Gain;
- Difference;
- Split Channels.

Use **Submit Current Pair** after the Setup status reports the pair is eligible.

### Submit Folder Pair

Folder Pair is for deterministic bulk evaluation of two directories.

1. Choose **Folder A** and **Folder B**.
2. Use **Validate / Preview**.
3. Confirm the previewed Scene count/order.
4. Use **Submit Folder Pair**.

The current pairing rules are:

- immediate files only; no recursive subdirectory scan;
- symlink inputs are excluded;
- eligible types are PNG/JPG/JPEG/BMP;
- each folder is normalized to deterministic Unicode-NFC lexical order;
- both folders must have the same non-zero eligible file count;
- maximum 512 pairs/Scenes;
- sorted A and B entries pair by index;
- every A/B pair must have matching original dimensions.

The filenames do not have to be semantically equal. The validated deterministic
sorted position is the pairing authority.

Folder Pair preparation is independent from Files registration. A large batch can
be submitted without making all of its images Selected or resident in PixelScope.

### Shared-storage staging

If a source already lies under a configured Remote IQA root, PixelScope references
it by logical Root ID + relative path.

If a source lies outside the configured roots and a staging root is configured,
PixelScope may copy it to content-addressed staging based on SHA-256 before job
creation. The request still contains portable logical identity rather than the
original Windows path.

## Track Remote IQA Jobs

After submission, use the IQA **Jobs** tab. The local image workspace remains usable
while the remote job runs.

Jobs may pass through states such as:

```text
queued
preparing
extracting
aggregating
writing
succeeded
partial
failed
cancelled
```

The Jobs list shows job ID, submission kind, state, progress, and compact status/
error information.

### Cancel

Use **Cancel** for a non-terminal job when you want to request cancellation from the
server. The server owns the final state; cancellation can race with completion.

### Open Result

A successful/partial job does **not** automatically replace the current Results
view. This is intentional.

**Open Result** becomes available only after PixelScope has:

1. observed terminal `succeeded` or `partial`;
2. obtained the published schema-v2 logical result reference;
3. resolved that reference through the current Remote IQA storage-root mapping.

Click **Open Result** explicitly to open it through the same canonical result viewer
used by **File > Open IQA Result...**.

A temporary failure while retrieving the terminal result reference can recover
automatically without resubmitting the job. The job row remains terminal while the
client performs bounded retry. Create-job submission itself is not blindly retried,
because a connection error/timeout may occur after the server has already accepted
the job.

If a job stays terminal but Open Result cannot become available, inspect the compact
Jobs error. Typical categories are configuration, connection, timeout, HTTP,
protocol, or local storage-root resolution problems.

## Open and explore IQA results

Use **File > Open IQA Result...** to open an already-published Remote IQA result
directory directly, or use **Open Result** from a tracked job. Both paths reuse the
same Results workspace.

The IQA workspace is non-modal, so the existing image workspace remains available
while the result is explored.

For current schema-v2 results, open is **summary-first**. PixelScope reads the small
manifest/summary artifacts and initially shows **Absolute measurements** without
opening every Scene grid. The Dataset Overview uses the published pooled weighted
mean, while the hierarchy and Scene Trend expose the published Scene-level absolute
measurements for every declared variant.

The **Reference** control is local to the IQA workspace and is independent from the
image viewer's Primary state. A schema-v2 result may contain more than two variants.
Selecting a variant as Reference starts background preparation of the required Scene
grid measurements. During that work the workspace reports loading/calculation state;
when preparation completes, the hierarchy and plots switch to target-versus-reference
relative values. Returning to an already prepared Reference reuses the derived scalar
results. If deferred grid loading or calculation fails, PixelScope restores the last
successfully presented Absolute/Reference mode instead of leaving the control and
plots with different semantics.

For power-valued attributes, relative results are displayed in dB and the aggregation
control selects either the ratio of pair-valid weighted means or the mean of finite
pair-valid grid log-ratios. Signed attributes use their signed engineering unit and
the canonical target-minus-reference calculation. The relative Dataset Overview is
the arithmetic mean of valid Scene comparison values.

Use the attribute visibility controls to reduce the plotted set. The hierarchy is
organized by attribute and Scene, and the Scene Trend supports hover/click selection.
Selecting a Scene updates the Scene cards. These cards show published variant/source
identity, relative path, hash, and related metadata only. They do **not** open those
paths directly as native PixelScope source images. Logical-root resolution, source
hash verification, native source Inspect, spatial overlay, and block inspection are
later P5-D work.

### PARTIAL results

A PARTIAL result contains a valid subset of successfully published Scenes plus
explicit diagnostics for requested Scenes that failed or were cancelled.

The Results tab shows a compact summary such as:

```text
Partial result · 3 / 4 Scenes succeeded
```

and lists failed/cancelled Scene diagnostics. The successful Scenes remain available
for the same Absolute/Relative exploration as a COMPLETE result.

A zero-success job is Failed/Cancelled rather than a PARTIAL result. An all-success
job is the normal Complete/Succeeded path.

Historical schema-v1 results remain read-only compatibility. They expose the
available two-source A/B comparison workflow and do not invent schema-v2 absolute
measurements.

The IQA dock uses the same **Float/Dock**, **Maximize/Restore**, and **Hide** title-bar
behavior as Plots. **View > Reset Workspace Layout** clears its persisted floating
geometry, re-docks it on the right, and hides it with the rest of the workspace reset.

Passive IQA result browsing and Jobs tracking do not change Files registration,
logical Selected, Current Comparison Page, Active/Primary image state, Difference,
Display Gain, source residency/preload, native analysis results, Session state, or
temporary Picks.

### Development-only Remote IQA debug tools

When `PIXELSCOPE_REMOTE_IQA_DEBUG=1`, additional developer validation controls may
appear. They are not part of the normal release workflow:

- **Inspect JSON · DEBUG** runs the production request-preparation path but stops
  before the job POST;
- **Replay JSON · DEBUG** injects a bounded logical terminal job/result reference and
  still requires explicit Open Result;
- `scripts/p5c_make_debug_result.py` creates deterministic schema-v2 COMPLETE/
  PARTIAL test artifacts;
- `scripts/p5c_localhost_iqa_server.py` runs a real localhost HTTP fault server for
  client contract testing.

The localhost server performs no GPU/IQA calculation. It returns a logical reference
to a deterministic existing result artifact so submission, polling, error handling,
result-reference retry, and Open Result can be tested before a real external service
is available.

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
Difference presentation are not independent pick identities. A Difference tile
shows a non-interactive **Derived** badge instead of Pick. Pick/Unpick/Clear
Selection therefore leave an existing Difference presentation unchanged.

**Keep Selection is a Difference reset boundary.** If a Difference is active when
Keep Selection commits the picked subset, PixelScope closes that active Difference
before replacing Selected. This happens even when both of the old A/B source images
are included in the kept subset. After Keep, no active Difference document or A/B
provenance is bound to the new workspace and the toolbar **Diff** action is unchecked
and disabled.

Keep Selection does not purge the generation-keyed Difference Map Cache or change
source generations. To establish a Difference again, choose a valid current-page
Image 1/Image 2 pair in the Difference panel and explicitly use **Calculate**. A
matching cached generation pair is reused without recomputing the numerical map;
otherwise the normal Difference calculation runs. After a successful Calculate,
the toolbar **Diff** action controls visibility of that same active result only.
Hiding and showing it does not select a new pair or start another calculation.

Picking an image also does not decode or preload off-page images, protect them in
source residency, run Difference or analysis, or otherwise change the Current
Comparison Page working-set authority.

Only the explicit **Pick** control changes curation membership. Normal image pan,
Ctrl+drag ROI, Shift+drag Line Profile, and ordinary tile activation do not toggle
Pick state.

## Save and open Sessions

Use **File > Save Session...** to save durable workspace intent for later reuse.
PixelScope writes a `.pixelscope` JSON Session v1 artifact.

A Session can store:

- **Registered** native-source membership and minimum resolved RAW reconstruction
  metadata;
- exact ordered **Selected** paths;
- one Selected source-path anchor that reconstructs the Current Comparison Page;
- applicable source **Active** and page-local **Primary** state;
- stable layout mode;
- current shared ROI and Line Profile selection;
- current Display Gain;
- applicable Split Channels state;
- an eligible regenerable Difference recipe only when its A/B are both on the saved
  Current Comparison Page.

Temporary Picks are not persisted. Session also does not save decoded image arrays,
residency/LRU/preload state, workers/tokens/generations, calculated Statistics/
Histogram/Line Profile results, Difference maps/cache/generated result image, or
transient zoom/pan buffers.

Use **File > Open Session...** to restore a Session. PixelScope validates and stages
incoming identities before replacing the current logical workspace. It restores the
saved page and foreground-loads only that bounded Current Comparison Page through
the normal loader, then restores applicable presentation/analysis intent through the
existing Display Gain, Split, ROI/Line, and Difference paths. If an eligible
Difference recipe exists, Open restores its exact compatible options and issues one
explicit **Calculate**; Session does not pre-bind a Difference result.

If some saved paths are missing, loadable sources are restored and a compact warning
reports unavailable entries. If none can be registered, the existing workspace is
left unchanged. Corrupt files, unsupported/future schema versions, wrong artifact
kind, invalid paths/layout, or invalid embedded RAW metadata are rejected before
logical workspace replacement.

Session v1 identifies sources by normalized **absolute local paths** and does not
relocate or fuzzy-match moved files. A `.pixelscope` file may reveal local filesystem
path names, so review it before sharing outside the intended environment.

Legacy P4-B `pixelscope-comparison-set` v1 files remain readable through
**Open Session...**, but there is no separate current Open/Save Comparison Set UI.
Legacy Comparison Sets contain the narrower Selected/Active/Primary/layout/RAW
contract and do not gain Session-only fields retroactively.

### Open Recent

The File menu provides typed **Open Recent Images**, **Open Recent Folders**, and
**Open Recent Sessions** submenus. Each keeps at most ten path entries.

- Recent Image repeats normal direct-image selection intent.
- Recent Folder repeats registration-only folder intent.
- Recent Session delegates to normal Session Open.
- Missing paths offer explicit **Remove / Keep**.
- Existing wrong-kind or invalid Session artifacts stay in history until explicitly
  removed.

Recent history is best-effort path metadata; it does not own source, selection,
residency, Difference, or analysis state.

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
Session v1 persists the scalar Display Gain workflow intent and restores it through
the same presentation path; legacy Comparison Set v1 does not persist Display Gain.

## Cursor, ROI, and Line Profile selection

Moving over an image synchronizes the crosshair and status readout.

- Ctrl+drag creates one shared ROI; Esc clears ROI.
- Shift+drag creates a horizontal or vertical Line Profile selection.
- Shift+Esc clears the shared line.
- Alt+drag does not create a Line Profile.

ROI normalization, Statistics, Histogram, and Line Profile all use the Current
Comparison Page as the default analysis working set. Temporary Pick Set does not
extend or replace that analysis working set. Session v1 persists/restores the current
active ROI and Line selection; it does not add named/multiple ROI management.

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
membership does not change either authority and Pick/Unpick/Clear Selection does
not calculate, remove, or invalidate Difference. Difference is derived from its A/B
sources, never an independent Pick or logical Selected member.

When **Keep Selection** commits a new Selected subset, any active Difference is
closed unconditionally before the Selected mutation, even if its old A/B sources
both remain in the kept subset. The active Difference document/provenance is cleared
and toolbar **Diff** remains unchecked and disabled. The generation-keyed cache is
preserved and source generations are unchanged.

A new active Difference is established only by an explicit **Calculate** request
for the current Difference Image 1/Image 2 pair. Calculate performs the normal
compatibility checks and generation-aware cache lookup first. A cache hit is reused
without numerical-map recomputation; a miss uses the normal asynchronous
calculation. On success, the result becomes the active Difference and toolbar
**Diff** becomes enabled and checked.

After Calculate, toolbar **Diff** is visibility-only: unchecking hides that same
active result and checking it again shows the same result. The toolbar does not infer
a different A/B pair from the current page, does not promote an unrelated cached
result, and does not calculate implicitly.

When all six source slots of a Comparison Page are occupied, a successfully
established Difference result uses the existing Diff-only Single View presentation
and workspace-restore behavior. A cache hit obtained through explicit Calculate
uses the same presentation path as a freshly calculated result.

Legacy Comparison Set v1 does not persist Difference. Session v1 may persist only an
eligible regenerable current-page Difference recipe; it does not persist the map,
cache, or generated result image.

## Export analysis results

The File menu keeps **Export Statistics CSV...** and adds three focused exports:

- **Export Histogram CSV...** saves the exact current plotted Histogram series. CSV
  rows identify Full image/Active ROI scope and bounds, source/series/channel,
  native bin edges and raw count, current displayed bin edges, and current X/Y
  modes. Gray, RGB, and Bayer follow the same currently plotted series semantics.
- **Export Line Profile CSV...** saves the exact current plotted samples with line
  coordinates, source/series/channel, current X/Y modes, sample index/position, and
  current displayed value.
- **Export Difference Image...** saves PNG only when an explicit **Calculate** has
  established an active Difference result. The PNG comes from the current Difference
  presentation, so current Absolute/Mask, threshold, Difference Gain, and compatible
  channel presentation are reflected. It contains no toolbar/window chrome.

These commands do not recalculate analysis merely for export. In particular, a
Difference cache entry by itself does not make Difference export available and
export never calls Calculate. Export also does not load/reload sources, change
Selected/Active/Primary/Page, bump source generation, alter Difference cache
identity, or create preload/residency ownership.

The dialogs reuse **Default Export Folder** and the existing last-used-folder
fallback. Cancelling leaves the workspace unchanged. A failed write reports a short
status message and leaves the current analysis/workspace intact.

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

When opening a Session, saved resolved RAW profile metadata is restored before
foreground use. If the Session contains an unresolved RAW without saved profile
metadata, it remains unresolved and uses this same foreground resolution path.
Legacy Comparison Set v1 files use their compatible narrower RAW reconstruction
metadata through Open Session.

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

Open **Edit > Settings...**. Categories are **General**, **Files**, **Performance**,
and **Remote IQA**.

Application Settings schema is currently version 6. Session `.pixelscope` files,
legacy Comparison Sets, analysis exports, and typed Recent entries remain separate
from this application-settings schema.

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
normally reload when its page is revisited. Saving/opening a Session, exporting
analysis, or tracking a Remote IQA job does not create Selected-wide residency
protection.

**Difference Map Cache** is separate, default 128 MiB. Source eviction does not by
itself discard a valid generation-keyed Difference map. Keep Selection also does
not purge that cache when it closes the active Difference presentation for the new
Selected workspace. Difference export consumes the current presentation only and
does not mutate the cache.

**Preload Next Folder Position** remains exactly one valid one-to-six Selected
Folder Position ahead, direction +1, on a separate max-one worker. It does not
preload the next Comparison Page, Pick Set, Session, export target, or Remote IQA
batch. A physically RUNNING matching Folder Position preload may transfer to
foreground authority without duplicate decode. Unresolved RAW without a profile is
skipped rather than prompting from speculative preload.

Performance budget/preload changes are startup settings and display the restart-
required indication when they differ from current runtime values.

### Remote IQA

- **Server base URL** configures the remote IQA HTTP endpoint.
- **Root ID / Client path** rows map portable storage identities to paths available
  on this Windows machine.
- **Staging root** selects which configured logical root may receive content-addressed
  staging for outside sources.

Remote IQA storage paths are machine-local settings. They are not saved in Session v1
and are not embedded as server physical paths in IQA result artifacts.

**Reset Settings** resets application preferences including Remote IQA configuration.
**View > Reset Workspace Layout** resets workspace layout separately. Temporary Pick
state adds no Settings key. Typed Recent path history remains separate observer
metadata.

## Runtime Diagnostics

**Help > Copy Diagnostics** copies one deterministic sanitized snapshot. It reports
source residency, Difference cache usage, foreground/preload workers, preload
counters including promotion, stale results, and bounded recent accepted failures.

Diagnostics does not scan files, mutate selection, touch LRUs, start/cancel loads,
calculate Difference, or change presentation. Paths, credentials, traceback
context, and excess failure detail are sanitized.

## Plots and IQA docks

The Plots title bar provides Float/Dock, Maximize/Restore, and Hide. Histogram /
Line Profile selected tab and floating geometry are restored separately from
application Settings.

The IQA dock follows the same workspace title-bar behavior. Its Setup/Jobs/Results
workflow is non-modal, and **View > Reset Workspace Layout** returns it to the normal
docked/hidden baseline along with the rest of the workspace reset.
