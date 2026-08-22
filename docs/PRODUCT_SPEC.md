# Product specification

PixelScope is a CPU-only Windows engineering tool for rapid visual and numeric
comparison of PNG, BMP, JPEG, and profile-described RAW images. The workflow is
selection-driven for analysis while the Files workspace may register a much larger
catalog than the viewer works on simultaneously.

## Implemented workflow

### Registration, selection, Current Comparison Page, presentation, and residency

These terms have distinct product meanings:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset
Current Comparison Page
    ↓ viewer representation
Presented
    ↓ source lifecycle
Resident when required
```

- **Registered** means known to the Files workspace/catalog. Registration is not
  capped by the six-image comparison working set.
- **Selected** means the ordered logical comparison set. Selected may contain more
  than six images.
- **Current Comparison Page** is a derived maximum-six working subset of Selected.
  Page membership follows Selected ordering and page offset; it is not a second
  independently owned document collection.
- **Presented** means the current viewer representation. Multi View presents the
  current page; Single View presents one active image within that page.
- **Resident** means decoded native source is currently retained under the P2
  source-memory budget because current runtime correctness requires it.

`Analysis Working Set = Current Comparison Page`.
Viewer slots are always local `1..6` within the Current Comparison Page. Global
Selected ordinal and viewer slot are distinct concepts.

Registration does not imply selection, page membership, presentation, decode, or
residency. Selected membership alone does not imply residency.

### Image and folder input

PixelScope exposes **Open Images...** for selection-oriented image input and
**Open Folder...** for native single-folder registration. Multiple folders remain
registration-only through folder drag/drop or the registration API. Supported
images are:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

The file picker displays `Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)`.
There is no separate top-level RAW-open command and unsupported extensions are not
silently interpreted as RAW.

**Open Images...** supports multi-file selection. Every supported selected file is
registered and becomes part of the ordered Selected set. If more than six files are
supplied, none are discarded: the initial Current Comparison Page contains the
first six and later pages preserve the same Selected membership/order.

**Open Folder...** uses the native single-folder picker and registers one existing
directory per invocation. Multiple folders remain supported through folder
drag/drop or the registration API; when multiple paths are supplied there, resolved
paths are deduplicated and ordered deterministically. Folder registration has no
artificial six-item limit. Supported immediate contents are registered in Files,
but current Selected, Current Comparison Page, and presentation are not changed and
no first image is automatically selected. Two folders are never a special comparison
command. Folders with no supported images are skipped without failing other inputs.

Drag/drop preserves the same intent split:

- direct image files → register + make them the Selected set;
- folders → register only;
- mixed direct files + folders → direct files become Selected while folder
  contents are registered only.

`.json` sidecars are metadata for exact same-basename RAW inputs and never appear
as independent image documents. Files remain grouped by parent folder with natural
order and loading/resident/error indicators.

A stable state with registered documents and zero Selected documents is supported.
The central workspace prompts **Select an image from Files to view**. A truly empty
workspace instead prompts **Drop images or folders here** and exposes Open Images
and Open Folder actions.

### Current Comparison Page and navigation

For `Selected <= 6`, Current Comparison Page equals Selected. Existing production
Auto/Single/Multi behavior, primary semantics, number keys, Left/Right, ROI,
Statistics/Histogram/Line Profile, Difference, Folder Position, source residency,
and Folder Position preload remain the compatibility baseline.

For `Selected > 6`:

- pages are derived in six-image chunks from Selected ordering;
- page movement does not modify Selected membership/order;
- Multi View uses Current Comparison Page as its comparison workspace;
- large-selection Multi View keeps six-slot Grid 3x2 geometry on every page,
  including a short final page with unused slots cleared;
- Single View presents one active local slot while retaining the full current-page
  analysis/load context;
- keys `1..6` always select current-page local slots;
- Left/Right remains Previous/Next Selected Image across the complete Selected set;
- crossing a page boundary with Left/Right automatically changes the page so the
  active image remains in context;
- Ctrl+Left/Ctrl+Right moves Previous/Next Comparison Page; the application-wide
  shortcut is enabled only when that direction can move;
- Comparison Page navigation does not wrap at endpoints, and unavailable Ctrl+Arrow
  remains available to the focused control;
- the presentation-control row above the image workspace always exposes Page status
  and the current range/total, including a single page; previous/next arrows stay
  present and disable at unavailable endpoints;
- page navigation preserves the active local slot when possible and clamps it on a
  short final page;
- primary/focus presentation ordering is page-local and cannot change Selected
  ordering or page membership.

PageUp/PageDown remains exclusively Folder Position. Folder Position accepts only
one-to-six Selected documents from distinct folders. `Selected > 6` makes Folder
Position unavailable rather than applying it to only the current page.

### Review Selection & Curation

P4-A adds a temporary curation workflow without adding another source or analysis
authority:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
direct temporary Pick Set
    ↓ Keep Selection
new Selected subset
```

There is **no explicit Review Select mode**. Eligible native source tiles in Multi
View expose a stable **Pick** control directly. The first checked Pick captures the
current ordered Selected source IDs as the temporary baseline internally. The
button text remains `Pick`; checked membership is represented by its depressed
state and a bright-yellow tile-wide border. Normal tile activation, Primary, and
Pick membership remain independent states.

Picks survive Comparison Page navigation. A picked source may be off-page and need
not be decoded, resident, protected, preloaded, or presented. Pick Set membership is
not an analysis input and does not extend the Current Comparison Page working set.

The presentation row exposes the temporary curation state directly as
`Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection`.
`Selected N` is the temporary Pick Set count, not the Files logical Selected count.
**Clear Selection** clears only temporary pick membership. **Keep Selection** is
disabled when the Pick Set is empty. Only Keep Selection changes logical Selected:
it computes the new Selected set by filtering the captured baseline ordering by
picked membership, not by pick order. Non-picked images remain Registered in Files.
There is no user-facing Cancel command.

A different selection-oriented workflow that changes logical Selected after a
baseline has been captured invalidates the temporary baseline/Pick Set before or
with the inherited normal Selected mutation. Registration-only folder input does not
invalidate the curation state because it does not change Selected.

Pick identity is the native Registered/Selected source document ID. Split Channel
items, Difference derived documents, and gained preview representations are not
independent pick identities. A displayed Difference tile therefore exposes a
non-interactive **Derived** role instead of Pick; it has no independent curation or
logical Selected membership.

Pick, Unpick, and Clear Selection do not reconcile Difference because they change
only temporary workflow state. A successful **Keep Selection** is instead an
unconditional active-Difference reset boundary. If Difference is visible, Keep first
uses the existing PR #32 teardown/restore path, then clears active Difference
presentation/binding/provenance before applying the ordered kept Selected subset.
This happens regardless of whether the previous A/B sources survive the new
Selected set. Immediately after Keep, toolbar `Diff` is unchecked and disabled.

Keep does not purge generation-keyed Difference Map Cache entries, bump source
generations, or acquire curation-owned residency/preload authority. The next active
Difference must be established by an explicit **Calculate** request in the Difference
analysis UI for a valid current-page A/B pair. Calculate uses the existing
generation-aware cache first: a cache hit reuses the numerical map without redundant
map calculation; a miss uses the existing asynchronous Difference path. After
successful Calculate, toolbar `Diff` controls visibility of that same established
result only; hiding/showing it does not infer another pair or calculate again.

Ordinary source viewer/header presentation and Difference Image 1/Image 2 selector
text remain unchanged and Current Comparison Page scoped. Difference result headers
may use the existing page-local slot visualization, but page identity is not a
survival policy and does not become document/cache/Pick identity.

The captured baseline/Pick Set is temporary application-session workflow state. It
is not persisted to Settings/QSettings and does not own source arrays, previews,
residency/LRU state, caches, workers, RAW profile copies, source generation,
preload, Difference, or analysis requests.

### Comparison Set persistence — legacy read compatibility

P4-B introduced an explicit user-managed **Comparison Set** artifact before the
broader P4-C Session format. P4-C supersedes current writes and File-menu terminology
with Session v1 while preserving Comparison Set v1 read compatibility through
**Open Session...**.

The artifact uses extension `.pixelscope`. Version 1 is JSON with
`kind = "pixelscope-comparison-set"` and `schema_version = 1`. Persisted native-source
identity is a normalized **absolute local path**. Blank or relative source/Active/
Primary paths are rejected before normalization, and v1 does not relocate or fuzzy-
match moved files. Comparison Sets are therefore deterministic but machine/path-
layout dependent; sharing one can reveal local filesystem paths.

Save persists only durable logical comparison intent:

- ordered logical Selected native-source references;
- optional selected Active source;
- optional applicable current-page Primary source;
- stable layout mode;
- minimum resolved RAW profile metadata needed to reconstruct a RAW source.

Historical P4-B Save used logical Selected, never the temporary P4-A Pick Set. If
Picks existed but **Keep Selection** had not been applied, the original Selected set
was saved. After Keep, the curated Selected subset was the logical set and was saved.
Saving did not apply/clear Picks, force RAW profile resolution, decode off-page
members, or acquire Selected-wide source residency/protection.

Open validates the artifact before logical workspace mutation. Loadable saved
sources are registered through the normal input path and replace logical Selected in
saved order while unrelated Registered sources remain. Saved Active determines the
derived Current Comparison Page; only then is an applicable Primary restored, along
with stable layout. Current Comparison Page/page offset itself is never serialized.

Missing source paths partially load with a compact warning. If zero saved sources are
loadable, the existing logical workspace is unchanged. Corrupt JSON, wrong kind,
future schema, invalid path/layout, or invalid embedded RAW profile is rejected
without beginning source registration or foreground loading.

Resolved RAW reconstruction metadata is restored before foreground use. Unresolved
RAW remains unresolved and follows the existing lazy foreground resolution path;
Save did not force it to resolve.

Comparison Set persistence owns none of decoded source arrays, source
residency/LRU/protection, preload or promotion state, Difference maps/cache, Display
Gain state/previews, Statistics/Histogram/Line Profile/Difference request state,
workers/tokens/generation, Split/Difference derived documents, transient zoom/pan,
ROI/Line state, or temporary Pick state. Settings schema remained version 5 at the
P4-B boundary because `.pixelscope` is an external artifact, not application-settings
storage.

### Session persistence and typed Recent

P4-C merged as PR #31 at `436033a0d99513fe8db35f08305395127e430af2`.
Current `.pixelscope` writes use **PixelScope Session v1** with
`kind = "pixelscope-session"` and `schema_version = 1`. The authoritative external
artifact contract is `docs/SESSION_CONTRACT.md`.

Session v1 persists durable workspace intent:

- Registered membership plus minimum resolved RAW reconstruction metadata;
- exact ordered Selected paths;
- one Selected source-path Current Comparison Page anchor;
- applicable source Active and Primary plus stable layout;
- shared ROI and Line;
- Display Gain and applicable Split Channels state;
- a regenerable Difference recipe only when its A/B both belong to the saved Current
  Comparison Page.

Session does not serialize decoded arrays, source residency/LRU/protection, previews,
preload/workers/tokens/generations, Difference maps/cache/generated results,
calculated Statistics/Histogram/Line Profile results, or temporary Picks. Open
validates and stages incoming identities before destructive replacement, then
foreground-loads only the reconstructed Current Comparison Page through the inherited
loader. An eligible Difference recipe restores panel intent and issues one explicit
**Calculate**; Session never pre-binds active Difference provenance.

Current File UX exposes **Open Session...**, **Save Session...**, and typed bounded
**Open Recent Images/Folders/Sessions** submenus. Recent history is max-10, path-only,
best-effort observer metadata. Image, Folder, and Session activation delegate to
their canonical workflows; missing paths use explicit Remove/Keep. Recent history
was introduced outside Settings schema v5 and owns no source/runtime state.

### RAW input resolution

Ordinary PNG/BMP/JPEG inputs register without RAW profile UI. Direct RAW file
opening/drop must resolve a validated profile first:

- same-basename sidecar present: parse/validate it and preserve the current
  confirmation and exact/minimum-size policy;
- no sidecar: open the editable RAW Profile dialog;
- invalid sidecar: warn and open editable fallback instead of applying invalid
  metadata;
- cancelled direct-file profile dialog: do not register that RAW document;
- multi-file direct RAW open: resolve each selected RAW independently.

Folder registration uses a lazy RAW boundary to avoid repeated dialogs while
registering datasets. A RAW path and deterministic same-basename sidecar path may
be registered as a pending catalog document without resolving the profile or
decoding source.

A folder-registered unresolved RAW may also be Selected or Picked while off-page.
Selected/Picked membership alone does not prompt, decode, or require residency.
Profile resolution occurs when foreground Current Comparison Page work actually
requires that RAW. Unresolved RAW is not speculatively preloaded until a profile is
resolved.

Within one foreground presentation attempt, an unresolved RAW may prompt at most
once. Cancel leaves it registered/pending, starts no worker, and passive rerenders
do not immediately re-open the dialog. A later explicit foreground user action may
retry profile resolution.

PixelScope does not infer a profile from byte size or other weak evidence. The
product does not automatically reuse the previous RAW profile, apply one profile to
all selected RAW files, or pick a profile from byte size alone.

### Workspace and analysis

- Ordered Selected membership is independent from total Files registration count.
- Current Comparison Page is the default working set for Statistics, Histogram,
  Line Profile, selection-derived Difference inputs, ROI/Line normalization,
  foreground page-load completion, and current-page source protection.
- Temporary Pick Set does not replace or extend the Current Comparison Page analysis
  working set.
- Difference's explicit Image 1/Image 2 pair remains feature-owned authority.
- Up/Down retains Files-tree row navigation. Left/Right changes the active image
  across the complete Selected set.
- Files-tree `+` / `-` retains Qt-native folder expand/collapse. Display Gain
  `+` / `-` is scoped to the image-presentation subtree.
- Auto, Single, and Multi View retain synchronized cursor, zoom, offset, ROI, and
  line coordinates.
- Fixed two/three/four/five/six-image presentation layouts remain for
  `Selected <= 6`; large selections use fixed six-slot page geometry.
- **Split Channels** derives a transient R/G/B or R/Gr/Gb/B presentation working
  set from one Selected source. Multi View exposes explicit subchannel Primary;
  Single View navigates the same local subchannels. Files selection and native
  Current Comparison Page analysis remain source-owned.
- Structured status reports active file, format/resolution, coordinate, pixel
  value, zoom, and background work.
- Statistics uses explicit image/channel fields and full-image/ROI scope.
- Histogram supports Auto/256/1024/4096 bins with Count, Normalized, and Log count.
- Line Profile uses primary→active→first-displayed reference priority in
  Difference-from-reference mode.
- RGB and Bayer R/Gr/Gb/B analysis; RGBA alpha is ignored.
- Order-independent Difference cache keeps native compact maps for equal effective
  bit depth and normalized float32 maps for mixed effective bit depth, plus
  Absolute/Mask display, ROI metrics, LRU eviction, diagnostics, and a
  startup-configurable byte budget.
- Resizable/floating Plots dock retains persisted workspace state.

A derived Difference result uses the existing six-source Diff-only presentation
contract when all six Current Comparison Page source slots are occupied. Fresh
asynchronous results and cache hits use the same Diff-only Single View presentation
and workspace-restore semantics.

Folder-only registration is not a presentation lifecycle operation: it must not
reset Selected, Current Comparison Page, layout, active/primary state, ROI, Line
Profile, Difference presentation/cache, Display Gain, zoom/pan preservation state,
source-residency ownership, or captured temporary curation state.

### Analysis export productivity

P4-E adds focused reuse of results PixelScope already calculates or presents. File
menu keeps **Export Statistics CSV...** and adds:

- **Export Histogram CSV...** for the exact current plotted Histogram series. The
  artifact identifies Full image/Active ROI scope and bounds, source/series/channel,
  native bin edges and raw counts, current displayed bin edges, and current X/Y
  modes in stable deterministic order.
- **Export Line Profile CSV...** for the exact current plotted Line Profile series.
  The artifact identifies line coordinates, source/series/channel, current X/Y
  modes, sample index/position, and current rendered value in stable deterministic
  order.
- **Export Difference Image...** for an explicitly established active Difference
  result. PNG is encoded from the current Difference presentation preview, so it
  reflects current Absolute/Mask, threshold, Difference display gain, and compatible
  channel presentation without including toolbar/window chrome.

Export does not recalculate Histogram, Line Profile, or Difference, load/reload
source, promote residency, preload, bump source generation, or alter Difference-cache
identity. Difference PNG encoding/file I/O reuses the existing bounded analysis
worker pool; CSV serialization consumes already-computed in-memory series. The
existing configured Export directory is reused. Missing/in-flight results are
unavailable or safe no-ops, Cancel mutates nothing, and failed writes leave the
workspace unchanged. No new generic export framework is added.

### Remote IQA result and submission workflow

P5-A2 schema v2 is the executable result contract. P5-B / PR #38 is merged and owns
the canonical local result workspace. P5-C / Draft PR #42 extends that same IQA dock
with remote Setup and Jobs; it does not create a second result parser or local source
workspace.

The product surface is one non-modal IQA workspace:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

The dock retains the same float/dock/maximize/reset workspace behavior as Plots.
Users may also continue to use **File > Open IQA Result...** for an already-published
result directory.

#### Setup — Current Pair

Current Pair submits exactly two variants, `A` and `B`, from the **underlying Current
Comparison Page documents**. The product requires exactly two eligible source images
with matching original dimensions.

Submission identity is independent from:

- Primary;
- Active;
- viewer tile reorder;
- Single/Multi presentation;
- Display Gain;
- Difference;
- Split Channels.

Remote submission currently supports PNG/JPG/JPEG/BMP only. RAW is explicitly
unsupported; PixelScope does not silently demosaic or convert RAW for the remote IQA
service.

#### Setup — Folder Pair

Folder Pair evaluates two directories without turning the entire batch into local
Files/Selected/source-residency ownership.

The user chooses Folder A and Folder B, then **Validate / Preview** before submit.
Eligible files are immediate children only: no recursion and no symlink input. Each
folder is normalized to deterministic Unicode-NFC lexical order. The folders must
contain the same non-zero eligible count, at most 512 images, and items pair by
sorted index. Each resulting A/B pair must have equal original dimensions.

Folder filenames do not need to be semantically identical; deterministic sorted
position is the pairing authority.

#### Portable shared-storage identity

Client and server may mount the same shared storage at different physical paths.
PixelScope therefore sends logical identity rather than Windows paths:

```text
storage_root_id + relative_path + sha256 + width + height
```

A source already under a configured logical storage root is referenced in place.
A source outside configured roots may be staged under the configured staging root
using content-addressed SHA-256 identity.

Machine-local drive/UNC paths are configuration only. They are not serialized as
portable job/result identity, and PixelScope does not store server physical paths or
credentials in the result/session artifacts.

#### Jobs

Submission creates a durable remote job and switches to Jobs without blocking the
local comparison workflow. The client polls job state and displays progress/status.

Remote states include queued/preparing/extracting/aggregating/writing and terminal
`succeeded`, `partial`, `failed`, or `cancelled`.

Jobs exposes:

- **Cancel** while server state permits it;
- **Open Result** only when a succeeded/partial job has a published result reference
  that resolves through the current local storage-root mapping.

Completion never automatically replaces the current Results view. **Open Result is
always explicit** and delegates to the merged P5-B result controller.

Create-job POST is intentionally not automatically retried because an error or
timeout can occur after the server has already accepted the job. Idempotent terminal
result-reference retrieval is different: a transient failure can be retried in a
bounded sequence without resubmitting the job. A temporary result-reference failure
may therefore recover automatically while the Jobs row remains terminal.

#### Results

For schema v2:

- ordinary open is summary-first and reads only manifest + summary metadata;
- the initial mode is **Absolute measurements**;
- Absolute Dataset Overview uses server-authored `pooled_weighted_mean`;
- Reference selection uses stable N-way `variant_id`, independent from local Primary;
- all variants keep stable table/chart ordering across Absolute and Relative modes;
- Absolute mode is client-local state, not a reserved server variant string;
- an unprepared Reference loads/calculates in the background one Scene grid at a
  time and retains derived scalar results rather than the grid corpus;
- Relative mode uses the selected Reference as a presentation-only zero anchor while
  other values use canonical target/reference math;
- Relative Dataset Overview is the arithmetic mean of valid Scene comparison values;
- failed deferred Reference preparation restores the last valid presentation;
- Scene Trend and attribute filters browse published/derived result values without
  changing native PixelScope analysis;
- Scene cards show published source identity/path/hash metadata only. Native source
  opening, hash-verified Inspect, spatial overlay, and block inspection remain P5-D.

Schema v1 remains explicit historical read-only two-source compatibility and never
receives synthetic v2 absolute measurements.

#### PARTIAL results

A durable PARTIAL schema-v2 result preserves successful Scene work while reporting
failed/cancelled requested Scenes.

- `scene_outcomes[]` describes every requested Scene in original order;
- successful Scenes remain full valid schema-v2 Scenes;
- failed/cancelled outcomes carry bounded diagnostics;
- zero-success work is Failed/Cancelled rather than PARTIAL;
- all-success work is normal Complete/Succeeded.

Results shows a compact `successful / requested` partial summary and the failed/
cancelled diagnostics while keeping the successful Scenes available for normal
result exploration.

Passive IQA browsing and remote job tracking do not register/select/decode the
batch and do not change Files, Selected, Current Comparison Page, Active/Primary,
Difference, source residency/preload, Statistics/Histogram/Line Profile, or Session
state.

#### Debug-only validation surfaces

`PIXELSCOPE_REMOTE_IQA_DEBUG` enables development/contract-validation tools that are
not normal release workflow:

- Request Inspector — run production request preparation without POST;
- Replay JSON — inject a bounded logical terminal job/result reference without HTTP;
- deterministic schema-v2 fake-result generator;
- localhost real-socket fault server used to exercise the production HTTP client.

The localhost server performs no IQA calculation. It returns logical references to
known deterministic schema-v2 artifacts so the client can be exercised before the
external GPU service is available.

## Settings and runtime policy

`Edit > Settings...` currently uses **General / Files / Performance / Remote IQA**.
Application Settings schema is version 6.

**General** owns persistent RAW JSON confirmation, exact RAW file-size policy, and
Difference Threshold/Gain defaults. **Files** owns default Open/Export directories.
**Performance** owns Difference Map Cache MiB, Decoded Source Memory MiB, and preload
enablement.

**Remote IQA** owns machine-local client configuration:

- Server base URL;
- one or more shared-storage roots with **Root ID** and **Client path**;
- optional staging root selection from those logical roots.

Remote IQA mappings are live application configuration rather than Session v1 state.
`Reset Settings` resets schema-owned Remote IQA configuration together with the
other application settings; workspace layout reset remains separate.

Comparison Set/Session artifacts and analysis exports remain external files and do
not become `ApplicationSettings` state. Typed Recent path history remains separate
QSettings observer metadata.

Decoded Source Memory accounts native resident `ImageDocument.source` arrays only
and uses protected soft-budget LRU semantics. Source eviction and Difference cache
ownership remain independent. Registration, remote batch membership, and off-page
Selected/Picked membership do not make source data resident.

For large logical selections, **Selected alone is not a source-protection owner**.
Pick membership is also not a protection owner. Current Comparison Page plus
correctness dependencies such as foreground load, promoted foreground preload,
explicit Difference dependencies, and non-reloadable sources are protected.
Selected/Picked-but-off-page resident sources may therefore be evicted under the P2
budget and normally reload when their page is revisited. Session persistence, export,
and Remote IQA tracking do not introduce Selected-wide protection.

**Preload Next Folder Position** remains exactly `+1`, one valid one-to-six Selected
Folder Position deep, on a dedicated max-one worker; an exact matching physically
RUNNING preload may transfer logical authority to foreground without duplicate
decode. P5-C adds no Remote-IQA-driven source preload system.

## Difference contract

Difference compatibility is family-based: Gray compares only with Gray,
RGB/RGBA compares only with RGB/RGBA with alpha ignored, and Bayer compares only
with Bayer of the same CFA pattern. Cross-family, dimension-mismatch, CFA-mismatch,
and unsupported layouts are rejected; PixelScope performs no implicit RGB→Gray
conversion. Gray exposes `Gray`; RGB/RGBA exposes All/R/G/B; Bayer exposes
Mosaic/R/Gr/Gb/B.

Equal effective bit depths use the native code domain and preserve compact
uint8/uint16 absolute maps where applicable. Mixed effective bit depths
independently normalize each source by `(1 << bit_depth) - 1` and store the
absolute Difference as float32 in `[0,1]`. This normalization deliberately
ignores RAW Black/White levels, Display Gain, display transforms, preview values,
and demosaic. Cache metadata records domain/data range so reversed-pair reuse
cannot change threshold or metric semantics.

Threshold uses `code` in the native domain and `%FS` in the normalized domain;
mask comparison remains strict `>`. Persisted Settings Threshold remains the
native-domain code default. Normalized threshold is session-local.

Difference owns its own independent presentation Gain. General Display Gain is
not applied to Difference numerical sources, Difference preview generation, or
Difference-cache identity. Pick/Unpick/Clear Selection does not calculate
Difference, change its explicit pair authority, or invalidate a generation-keyed
Difference cache. Difference is a derived presentation rather than a logical
Selected or independently Pickable member.

Keep Selection always closes and clears the active Difference presentation/binding/
provenance before applying the new logical Selected subset, even when the old A/B
sources both survive. Cache entries and source generations remain unchanged. The
next active Difference is established only by explicit Difference **Calculate** for
a valid current-page pair. Calculate performs the existing generation-aware cache
lookup first and reuses a hit without redundant numerical map calculation; a miss
uses the existing asynchronous calculation. Once established, toolbar `Diff`
controls visibility of that same active result only and must not infer another pair
or trigger calculation.

Legacy Comparison Set v1 does not persist Difference pair/map/cache state. Session
v1 may persist only an eligible current-page regenerable Difference recipe, never the
map/cache/generated result. P4-E Difference export consumes the current established
presentation preview only; it does not call Calculate or promote an inactive cached
map into active Difference state.

## Display Gain contract

P3-B introduced the generic presentation primitive and P3-C generalized its viewer
activation:

```text
display = anchor + gain * (source - anchor)
```

The numerical core is not RAW-specific. It accepts a caller-supplied scalar
anchor, naturally supports `anchor=0`, uses float32 affine processing, and may be
applied to selected channel views. It never modifies native source data.

PixelScope exposes one application-session **Display Gain** control with:

```text
1× / 2× / 4× / 8× / 16×
```

The value is shared across supported Single/Multi View tiles. It is not persisted to
application Settings or RAW profiles; Session v1 persists the scalar workflow intent
and restores it through the existing Display Gain runtime path. Legacy Comparison
Set v1 does not persist Display Gain.

Document policy is:

- ordinary Gray/RGB use `anchor=0`;
- ordinary RGB split-channel views use `anchor=0` on their native source plane;
- RGBA applies gain to RGB only and preserves canonical 1× alpha exactly;
- RAW keeps the P3-B Black-derived anchor rules;
- Difference is excluded because it owns its own presentation Gain.

Gain 1× is a strict fast path: PixelScope reuses canonical
`ImageDocument.preview`, schedules no full-frame gain worker, and retains no
additional gained preview. Gain >1 derives only viewer-local preview from already
resident source on the existing shared numerical pool.

Display Gain is presentation-only. Pixel inspection, Statistics, Histogram, Line
Profile, Split Channel source arrays, Difference, generation, source residency,
and cache identity remain independent of it. `+` / `-` gain shortcuts are scoped
to the image-presentation subtree so Files retains native key behavior. Pick
identity remains the native source document ID rather than a gained preview.

## RAW profile and decode contract

RAW profile resolution is conditional logic inside the unified image-input
workflow; it is not a separate top-level file-opening mode.

A same-name JSON sidecar may pre-fill/resolve the profile. The General Settings
preference may skip repeated confirmation only when that sidecar is valid and the
configured exact/minimum file-size policy matches. When **Require Exact RAW File
Size** is disabled, RAW files may contain trailing bytes but may not be
undersized. When enabled, byte count must exactly match the profile requirement.

The RAW Profile dialog exposes **Load Profile...** and **Save Profile...**. JSON
remains the storage format and existing migration behavior is preserved. The
profile separates:

- storage format: unpacked, MIPI RAW10, RAW12, or RAW14;
- sample container for unpacked data: `uint8` or `uint16`;
- effective bit depth;
- byte order and LSB/MSB alignment where applicable;
- width, height, offset, stride, and grayscale/Bayer layout;
- Bayer pattern;
- `black_level` and `white_level` metadata, including R/Gr/Gb/B Black tuples for
  Bayer profiles.

The same RAW path may be resolved again with corrected profile settings while
retaining document identity/reload semantics.

The current product deliberately has no global RAW profile database, Settings-
owned profile collection, favorites, rename/duplicate/delete manager, profile
search UI, file-size-only or fuzzy suggestion, sensor-model inference, Bayer
pattern inference, or automatic Black/White estimation. Exact same-basename
sidecars remain supported because they are deterministic file-local evidence.

Decoded samples in `ImageDocument.source` are the native RAW authority. Pixel
inspection, Statistics, Histogram, Line Profile numerical data, Split Channels,
Difference, preload/reload identity, and source residency operate on those native
samples regardless of Display Gain or Pick membership.

Current Session v1 may store minimum **resolved** RawProfile metadata needed to
reconstruct saved RAW sources; legacy Comparison Set v1 has compatible reconstruction
metadata. Neither persistence path changes native-source semantics or forces an
unresolved RAW to resolve during Save.

## RAW display contract

RAW display is explicitly separate from analysis:

- at `Display Gain = 1×`, display range is native code
  `0..((1 << bit_depth) - 1)`;
- `black_level` is not subtracted from 1× display and `white_level` is not used as
  display maximum;
- gained RAW uses a Black-derived anchor, equivalently `B + G * (X - B)`;
- RAW Gray scalar Black is the scalar anchor;
- schema-valid GRAY four-value Black remains compatible and uses legacy
  `min(black_level)` as the global display anchor;
- Bayer tuple Black uses CFA-specific R/Gr/Gb/B anchors; scalar Bayer Black applies
  one anchor to all channels;
- split Bayer planes use the corresponding named-channel Black anchor;
- Bayer anchor processing does not create a full-size Black map;
- gain/range mapping uses float32 fused affine processing where possible and
  clipping occurs at final display conversion;
- `white_level` remains metadata only.

Gain changes regenerate only derived viewer presentation from resident source.
They do not reload/decode native RAW, change source residency ownership, bump
source generation, or change Difference cache identity.

Packed formats own their byte layout and fixed bit depth, so container,
endianness, and alignment controls do not apply. Bayer is analyzed as native
mosaic planes. Demosaic, white balance, CCM, tone mapping, and processed-RAW
analysis are outside the current product contract.

## Program status and future scope

P3 — Image Semantics & RAW Processing and P4 — Workflow & Session Productivity are
Complete. P5-0 / PR #36, P5-A schema-v1 / PR #37, P5-A2 durable/executable schema-v2
/ PR #39/#40, and P5-B IQA Workspace / PR #38 are merged. Current merged main is
`ad3721e28b759e75d8e0f4a28b003a4dd22f0f4a` after PR #41's formatting baseline.

P5-C **Submission & Shared Storage** / Draft PR #42 is Active. The major client
workflow—typed Remote IQA settings, portable root identity, Current/Folder Pair
submission, Jobs polling, explicit Open Result, executable PARTIAL results, debug
request/replay harnesses, real-socket localhost fault testing, and bounded terminal
result-reference retry—is implemented and under closeout.

P5-C still has pre-merge lifecycle/storage blockers: cross-process staging and
symlink/junction containment, cooperative cancellation of running preparation before
create POST, duplicate/ambiguous create handling without blind POST retry, and the
settings-remap/result-resolution race. Latest-head full validation and independent
whole-PR review are also required.

P5-D viewer-linked Scene/grid Inspect is blocked until P5-C merges. P5-E then adds
historical/recent result productivity, and P5-F owns real external-server/shared-
storage integration and measured performance/lifetime hardening. P6 owns identity,
access, credentials, permission, and remote operations. P7 owns release engineering
and distribution.

The earlier reusable Profile Library/suggestion plan remains deferred. It should
return only if actual workflow evidence justifies persistent profile management or
a deterministic suggestion model.

Additional RAW clipping/highlight/shadow or Bayer observability remains optional.
Demosaic remains deferred unless a future owner-approved processed-preview scope
defines white balance, color, tone, metadata, and analysis boundaries coherently.

Arbitrary-angle Line Profile is also deferred. Line Profile is an observation/
sampling tool, so a future arbitrary-angle design requires an explicit discrete
pixel-sampling/path and coordinate-display contract rather than implicitly adopting
interpolation.
