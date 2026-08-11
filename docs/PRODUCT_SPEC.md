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
independent pick identities.

The captured baseline/Pick Set is temporary application-session workflow state. It
is not persisted to Settings/QSettings and does not own source arrays, previews,
residency/LRU state, caches, workers, RAW profile copies, source generation,
preload, Difference, or analysis requests.

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

## Settings and runtime policy

`Edit > Settings...` uses **General / Files / Performance** category pages.
Settings schema remains version 5. P4-A adds no Settings/QSettings key and does not
persist the captured curation baseline/Pick Set.

General owns persistent RAW JSON confirmation, exact RAW file-size validation,
and native Difference Threshold/Gain defaults. Files owns optional default Open
and Export folders. Performance owns startup Decoded Source Memory, Difference Map
Cache, and preload settings.

Decoded Source Memory accounts native resident `ImageDocument.source` arrays only
and uses protected soft-budget LRU semantics. Source eviction and Difference cache
ownership remain independent. Registration and off-page Selected/Picked membership
do not make source data resident.

For large logical selections, **Selected alone is not a source-protection owner**.
Pick membership is also not a protection owner. Current Comparison Page plus
correctness dependencies such as foreground load, promoted foreground preload,
explicit Difference dependencies, and non-reloadable sources are protected.
Selected/Picked-but-off-page resident sources may therefore be evicted under the P2
budget and normally reload when their page is revisited.

**Preload Next Folder Position** remains exactly `+1`, one valid one-to-six
Selected Folder Position deep, on a dedicated max-one worker; an exact matching
physically RUNNING preload may transfer logical authority to foreground without
duplicate decode. P4-A adds no Comparison Page or Pick Set preload system.

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
native-domain code default under schema v5. Normalized threshold is session-local.

Difference owns its own independent presentation Gain. General Display Gain is
not applied to Difference numerical sources, Difference preview generation, or
Difference-cache identity. Pick/Unpick does not calculate Difference, change its
explicit pair authority, or invalidate a generation-keyed Difference cache.

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

The value is shared across supported Single/Multi View tiles and is not persisted
to application Settings, workspace state, or RAW profiles.

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

P3 — Image Semantics & RAW Processing is Complete through P3-E. PR #27 merged at
`835634a58609601605fd0fc18a3028b64225f535` after integration/presentation
hardening of the delivered Difference, RAW/display, Display Gain, unified input,
and Current Comparison Page contracts.

P4-0 merged as PR #28 at `e30c49d6759715228a820d673ad8939ea9a3afe8`.
P4-A Review Selection & Curation is implemented on
`feature/p4-a-review-selection-curation`; owner/local Windows runtime and requested
validation are reported PASS, and independent re-review found the prior runtime/test
blockers resolved. Durable-doc closure and merge remain pending, so P4-A is not yet
Complete.

Later planned P4 work covers persistent comparison sessions, typed recent-entry /
session-entry UX, Saved ROI productivity, focused viewer overlay/export productivity,
and integration hardening. P4-A does not begin P4-B persistence.

The earlier reusable Profile Library/suggestion plan remains deferred. It should
return only if actual workflow evidence justifies persistent profile management or
a deterministic suggestion model.

Additional RAW clipping/highlight/shadow or Bayer observability remains optional.
Demosaic remains deferred unless a future owner-approved processed-preview scope
defines white balance, color, tone, metadata, and analysis boundaries coherently.

Arbitrary-angle Line Profile is also deferred from P4. Line Profile is an
observation/sampling tool, so a future arbitrary-angle design would require an
explicit discrete pixel-sampling/path and coordinate-display contract rather than
implicitly adopting interpolation.

Later planned work includes remote IQA / image evaluation, heatmaps, and validated
standalone Windows distribution.