# PixelScope current state

Snapshot date: 2026-08-11
Current merged baseline / P4-A PR #29 merge commit:
`3486146494076e9b513843b90ec44e504043729e`

P4-B Comparison Set Persistence is implemented on
`feature/p4-b-comparison-set-persistence` / PR #30. The repository owner reports the
focused P4-B Windows validation PASS (`36 passed`). Independent review reports no
remaining runtime/schema/test blocker; merge closure is now limited to durable-doc
consistency plus the normal final validation/re-review gates.

## Merge baseline

- P1-D/P1-E/P1-F completed as PR #10–#12.
- P2-0 through P2-F completed as PR #13–#20; P2-F merged at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.
- P3-0 merged as PR #21.
- P3-A Difference Gray/mixed-bit support merged as PR #22.
- P3 roadmap replanning merged as PR #23.
- P3-B RAW Native & Display Semantics merged as PR #24.
- P3-C Display Gain generalization merged as PR #25.
- P3-D Unified Image Opening & RAW Profile Resolution merged as PR #26.
- P3-E Integration, Presentation UI Polish & Phase Hardening merged as PR #27 at
  `835634a58609601605fd0fc18a3028b64225f535`, completing P3.
- P4-0 P3 Closure & P4 Program Setup merged as PR #28.
- P4-A Review Selection & Curation merged as PR #29 at the current baseline SHA.

The active plan is [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).
P4 is **Workflow & Session Productivity**. P4-B Comparison Set Persistence is the
active implementation slice and is merge-pending on PR #30.

The completed P3 archive is
[`exec-plans/completed/p3-image-semantics-raw-input.md`](exec-plans/completed/p3-image-semantics-raw-input.md).

## Workspace ownership model

P3 distinguishes five runtime layers:

```text
Registered
    ↓ user selection
Selected
    ↓ derived page offset / fixed page size
Current Comparison Page
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

- **Registered**: known to the Files workspace/catalog. No artificial six-item limit.
- **Selected**: ordered logical comparison set. It may contain more than six images.
- **Current Comparison Page**: derived from Selected ordering plus page offset with a
  fixed maximum of six images. It is not a duplicated document collection.
- **Presented**: viewer representation of that working page. Multi View presents the
  page; Single View presents one active page-local slot.
- **Resident**: decoded native source held under the separate P2 source-residency
  budget when current correctness requirements need it.

`Analysis Working Set = Current Comparison Page`.
Viewer slot numbers are always local `1..6` within the Current Comparison Page;
global Selected ordinal and viewer slot are distinct concepts.

Registration count, Selected count, current-page size, presentation capacity, and
resident-source ownership are independent concerns.

## P4-A temporary curation state

P4-A adds one application-session temporary state layer beneath the Current
Comparison Page for curation workflow only:

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

`ReviewSelectionState` stores only an ordered snapshot of baseline Selected IDs, a
set of picked native source IDs, and an internal captured-baseline flag. It does not
store source arrays, preview arrays, resident/cache objects, workers, RAW profile
copies, Current Comparison Page copies, or derived Difference/Split documents.

There is **no explicit Review Select mode**. Eligible native source tiles in Multi
View expose a stable **Pick** control directly. The first checked Pick captures the
current ordered Selected IDs as the baseline. The Pick label remains `Pick`; checked
membership is communicated by the depressed/checked button plus a high-contrast
bright-yellow tile-wide border. Normal tile activation and Primary remain
independent. Picks persist across Comparison Pages and may refer to off-page Selected
sources without making those sources resident or protected.

The presentation row exposes temporary curation state directly as
`Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection`.
`Selected N` here is the temporary Pick Set count, not Files logical Selected count.
**Clear Selection** clears only temporary picks. **Keep Selection** is disabled at
zero picks and is the only curation action that changes Selected. The result is the
captured baseline Selected ordering filtered by picked membership, so pick order
never reorders the result. Non-picked images stay Registered. There is no
user-facing Cancel command.

If another workflow replaces/removes logical Selected membership after a baseline
has been captured, the temporary curation baseline/Pick Set is invalidated before or
with the existing normal Selected mutation. Registration-only folder input does not
invalidate curation state because it does not change Selected. Temporary curation
state is not persisted to Settings/QSettings.

Pick membership is **not** source ownership, decode authority, residency protection,
preload authority, analysis working-set authority, Difference input authority, or
presentation-source authority. Split/Difference derived documents are not
independent pick identities.

## P4-B Comparison Set persistence

P4-B introduces a small external **Comparison Set** artifact, not full application
session persistence. The file extension is `.pixelscope`; v1 is JSON with
`kind = "pixelscope-comparison-set"` and `schema_version = 1`.

Persistent identity is a normalized **absolute local native-source path**. The v1
reader rejects blank or relative `sources[].path`, `active_path`, and `primary_path`
values before normalization. There is no relocation or fuzzy path resolution in v1,
so a Comparison Set intentionally remains machine/path-layout dependent and may
expose local filesystem paths if the artifact is shared.

Save persists only durable logical comparison intent:

- ordered logical **Selected** native-source paths;
- optional selected **Active** path;
- optional applicable current-page **Primary** path;
- stable layout mode;
- minimum resolved RAW profile metadata when required to reconstruct a RAW source.

Temporary P4-A Picks are not serialized. If Picks exist but **Keep Selection** has
not been applied, Save writes the original logical Selected set. After Keep, it
writes the resulting curated Selected subset. Save neither applies nor clears Picks
and does not decode off-page Selected members or acquire residency/protection.

Open validates the artifact before logical workspace mutation, registers loadable
native sources through the normal path, replaces logical Selected in saved/loadable
order, and leaves unrelated Registered sources registered. Saved Active selects the
derived Current Comparison Page; an applicable Primary is then restored only on that
page, and layout mode is restored. Current Comparison Page/page offset itself is
**derived, never serialized**.

Missing sources use partial-load behavior with a compact warning. If no saved source
is loadable, the existing logical workspace is unchanged. Corrupt JSON, wrong kind,
future schema, invalid layout/identity, or invalid embedded RAW metadata is rejected
without registration/foreground-load mutation.

Resolved RAW profile metadata is restored before foreground use. Unresolved RAW
remains unresolved and follows the existing lazy foreground profile-resolution path;
saving does not force profile resolution.

Comparison Set persistence owns **none** of decoded source arrays, source
residency/LRU/protection state, preload plans/workers, Difference maps/cache, Display
Gain previews/state, analysis requests/results, worker/request/generation tokens,
Split/Difference derived documents, transient zoom/pan, ROI/Line state, or temporary
P4-A curation. Settings schema remains v5 because `.pixelscope` is an external
artifact rather than a SettingsRepository schema change.

## Unified input policy

Supported image inputs are exactly:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

The image picker filter is:

```text
Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)
```

### Open Images...

Selection-oriented input:

- multi-file selection is supported;
- all supported selected files are registered;
- registered direct files become the current ordered Selected set;
- Selected may exceed six without loss;
- initial Current Comparison Page is the first six Selected images;
- ordinary and RAW files share this command;
- RAW follows the existing profile-resolution contract before direct-open
  registration.

There is no separate **Open RAW with Profile...** action.

If a temporary curation baseline has been captured, a normal Open Images/direct-file
selection replacement invalidates that baseline/Pick Set before continuing with the
inherited selection semantics.

### Open Folder...

Registration-oriented input:

- the native picker selects one existing directory per invocation;
- multiple folders remain supported through folder D&D / the registration API;
- multiple supplied directory paths are deduplicated and ordered deterministically;
- practical folder registration count is not limited to six;
- supported immediate contents are registered in Files;
- current Selected set, Current Comparison Page, and presentation do not change;
- no first image is automatically selected;
- no two-folder comparison group is created implicitly;
- empty/no-supported-image folders are skipped and reported compactly.

Folder-only registration preserves layout, active/primary document, ROI, Line
Profile selection, Difference presentation/cache, Display Gain, existing view
state, source-residency ownership, and any captured temporary curation state because
it does not mutate Selected.

### Drag and drop

- dropped image files are registration + selection oriented, like Open Images;
- dropped folders are registration-only, like Open Folder registration;
- any folder count uses the same policy; there is no exactly-two-folder special case;
- mixed file + folder drop preserves both intents: explicit files become Selected
  while folder contents remain registered-only.

Unsupported files and standalone `.json` sidecars never become image documents.

## Registered but unselected state

`registered documents > 0` with `selected documents == 0` is a supported state.
The central workspace displays **Select an image from Files to view**. A truly
empty workspace instead displays **Drop images or folders here** with Open Images
and Open Folder actions.

## Current Comparison Page navigation

For `Selected <= 6`, Current Comparison Page equals Selected and existing production
behavior remains the baseline.

For `Selected > 6`:

- pages are derived in six-image chunks from Selected ordering;
- the presentation-control row above the image workspace shows Page status and
  selected range; previous/next controls remain present and disable at endpoints;
- `Ctrl+Left` / `Ctrl+Right` move one Comparison Page only while that direction is
  available; unavailable Ctrl+Arrow remains native to the focused control;
- `Left` / `Right` retain fine navigation across the complete ordered Selected set;
- crossing a page boundary with Left/Right automatically changes Current Comparison
  Page so the active image remains in context;
- number keys `1..6` address the local slot of the Current Comparison Page;
- coarse page navigation preserves the active local slot where possible and clamps
  it to the last available slot on a short final page;
- large-selection Multi View retains six-slot `Grid 3x2` geometry, so a short final
  page clears unused slots rather than changing page geometry;
- Single View displays one active image but its analysis/load context remains the
  full Current Comparison Page.

PageUp/PageDown are not reused for Comparison Page navigation. Temporary picks
survive page movement, but page movement does not derive from, preload, or protect
Pick Set membership.

## Presentation-row integration

The production application composes the P3-D/P3-E presentation row with the P4-A
direct curation controls. Command/state ownership remains in `MainWindow`, Display
Gain remains owned by its existing session state, and P4-A adds no separate mode or
contextual group.

Presentation row contract:

- Layout remains on the left with Auto / Single View / Multi View.
- Comparison Page uses compact programmatic high-DPI Previous/Next icons from the
  existing PixelScope icon infrastructure.
- Previous/Next are `QToolButton` controls with stable geometry, explicit disabled
  endpoint states, tooltips, accessible names/text, and `NoFocus` mouse-command
  behavior; Ctrl+Left/Ctrl+Right remain the keyboard command owners.
- Page index and Selected range remain fixed-width semantic labels, preventing
  endpoint or digit-count layout shift.
- Display Gain follows Page at 1×/2×/4×/8×/16× and is viewer-only.
- P4-A then exposes `Selected N | Clear Selection | Keep Selection` directly in the
  same row with normal command spacing; `Selected N` is the temporary Pick count.
- eligible Multi View native source tiles expose `Pick` directly; checked membership
  remains a stable label plus depressed state and bright-yellow tile-wide border.
- existing `design_tokens.py` colors, spacing, control height, border, and disabled
  text conventions define command-bar styling and Windows dark-UI contrast.
- the row remains distinct from the Main toolbar and directly above the image
  workspace.

## RAW registration boundary

Direct RAW open/drop preserves the P3-D contract:

- exact same-basename sidecar → parse/validate under confirmation and exact/minimum
  size policy;
- no sidecar → editable RAW Profile dialog;
- invalid sidecar → warning then editable fallback;
- cancel → no erroneous direct-open RAW registration;
- multiple RAW files resolve independently.

Folder registration is lazy for RAW. The RAW path and deterministic same-basename
sidecar path can be registered as a pending document without showing a dialog or
decoding source. An unresolved RAW that is Selected but off-page remains logical
selection only: it is not prompted, decoded, or made resident merely because it is
Selected. Being Picked adds no authority. Profile resolution occurs when it enters
the foreground Current Comparison Page and native source is required. Unresolved RAW
is excluded from speculative preload until a profile is resolved.

One foreground presentation attempt prompts an unresolved RAW at most once. Cancel
leaves it registered and pending, starts no worker, and passive rerenders do not
immediately reopen the dialog. A later explicit foreground action may retry.

No profile is inferred from file size or other weak evidence. The RAW dialog uses
**Load Profile...** / **Save Profile...** terminology. P3 adds no global Profile
Library, profile CRUD manager, last-profile reuse, apply-to-all behavior,
size-only/fuzzy matching, sensor/Bayer inference, or Black/White estimation.

## Navigation and analysis baseline

- PageUp/PageDown Folder Position operates only on one-to-six currently Selected
  documents from distinct folders. Other registered folders do not participate.
- `Selected > 6` makes Folder Position unavailable; PageUp/PageDown are a no-op
  with compact status rather than partially moving only the Current Comparison Page.
- Left/Right navigates the complete Selected set; Up/Down remains Files-tree
  navigation.
- Statistics, Histogram, Line Profile, selection-derived Difference context, ROI
  normalization, current-page load completion, and local slot mapping all use the
  same Current Comparison Page authority.
- Temporary Pick Set never replaces or extends that analysis working set.
- Feature-owned explicit Difference Image 1/Image 2 authority remains unchanged.
- ROI uses Ctrl+drag / Esc; Line Profile uses Shift+drag / Shift+Esc.
- Statistics, Histogram, Line Profile, Difference, and pixel inspection consume
  native source semantics rather than gained preview pixels. Split Channels derives
  a transient viewer-local R/G/B or R/Gr/Gb/B working set while Files selection and
  native analysis authority remain on the original Current Comparison Page source.
- Difference supports Gray, RGB/RGBA, and same-CFA Bayer with native/normalized
  domain rules established by P3-A.

## RAW and Display Gain baseline

Current RAW support includes unpacked uint8/uint16, MIPI RAW10/12/14, stride,
offset, endian/alignment, Gray/Bayer layout, JSON migration, same-path reload,
exact/minimum-size policy, and Black/White metadata.

Display Gain remains presentation-only:

```text
display = anchor + gain * (source - anchor)
```

- choices: 1×/2×/4×/8×/16×;
- ordinary Gray/RGB uses anchor 0;
- RGBA gains RGB only and preserves alpha;
- RAW 1× uses native effective full scale;
- RAW gain >1 uses `B + G * (X - B)` with existing Gray/Bayer Black rules;
- 1× reuses canonical preview;
- gain changes do not mutate source, analysis results, request identity, residency,
  or Difference.

P4-A does not change Display Gain workers, preview identity, RAW Black-anchored
math, or native Difference semantics. Pick state follows source IDs rather than any
gained preview representation.

## Runtime/settings baseline

Settings schema remains version 5. P4-A adds no Settings/QSettings key and does not
persist the captured curation baseline or temporary Pick Set. P4-B also does not
change Settings schema: Comparison Sets are explicit external `.pixelscope` artifacts.

Source residency remains exact native `source.nbytes` under P2 protected soft-budget
LRU semantics, with the P3-D large-selection refinement that **Selected alone is not
a protection owner**. Pick membership is also not a protection owner. The generic
bounded protection authority is the Current Comparison Page plus correctness
dependencies such as foreground loads, promoted foreground preload, and Difference
dependencies. Selected/Picked-but-off-page resident sources may therefore be evicted
and normally reloaded when revisited.

Difference cache remains independent. Preload remains +1 Folder Position, max-one
dedicated worker, with running-preload promotion as established by P2. P4-A does
not add Comparison Page or Pick Set preloading. P4-B does not serialize or acquire
preload/residency/cache authority. Diagnostics remain deterministic, bounded,
sanitized, and observation-only.

## P3 sequence — Complete

1. P3-A — Difference Gray / Mixed Bit-Depth Support — Complete — PR #22
2. P3-B — RAW Native & Display Semantics — Complete — PR #24
3. P3-C — Display Gain Extension — Complete — PR #25
4. P3-D — Unified Image Opening & RAW Profile Resolution — Complete — PR #26
5. P3-E — Integration, Presentation UI Polish & Phase Hardening — Complete — PR #27

## P3 closure evidence

P3-E independent review initially identified one production-composition integration-
test blocker. Follow-up changes added actual replacement `QToolButton` click wiring,
real Display Gain shortcut/focus ownership in the production composition, and Qt
teardown/recreation regression coverage. Independent re-review reported the blocker
resolved and found no remaining production/runtime/architecture blocker.

The repository owner reported the **full local Windows pytest suite PASS** on the
code/test head `1af4f6703656028ca7d0e2bdaf369cce029e4bb1`. The subsequent PR
head `b29963cbf91bf5c022a53d9562e36510e80112a2` changed only
`docs/AGENT_HARNESS_NOTES.md` and did not alter runtime or tests. PR #27 then merged
at `835634a58609601605fd0fc18a3028b64225f535`.

No Ruff, Ruff-format, mypy, pip-check, docs-check, or `git diff --check` PASS is
claimed here without separate observed evidence.

## Active P4 sequence

1. P4-0 — P3 Closure & P4 Program Setup — Complete — PR #28
2. P4-A — Review Selection & Curation — Complete — PR #29
3. P4-B — Comparison Set Persistence — implemented, focused owner validation PASS,
   merge pending — PR #30
4. P4-C — Comparison Set Entry UX / Recent Entries — planned
5. P4-D — Saved ROI & Analysis Workspace Productivity — planned
6. P4-E — Viewer Overlay & Export Productivity — planned
7. P4-F — Integration & Workflow Hardening — planned

P4 inherits the P2/P3 ownership and numerical contracts above. Temporary workflow
state must not become source/cache/residency/analysis authority.

Arbitrary-angle Line Profile is intentionally omitted from P4. Because Line Profile
is an observation/sampling tool, a future arbitrary-angle version should define a
discrete sampling/pixel-path and coordinate-display contract explicitly rather than
implicitly introducing interpolation. The current utility does not justify that
semantic/UI complexity.