# PixelScope current state

Snapshot date: 2026-08-15
Current merged baseline / PR #34 merge commit:
`79ee74134f1ebef9dd13f82e49f8e34407bb78f4`

P4-C **Session Persistence & Typed Recent** merged as PR #31 at
`436033a0d99513fe8db35f08305395127e430af2`. PR #32 runtime stabilization merged at
`e1ccf264f86e37b438c923faceae96c3ecb539b7`. PR #33 source-curation / Difference
semantics merged at `51a540c92c372d71e02fd849fb5e0d406d0e9327`. P4-E **Analysis Export
Productivity** merged as PR #34 at the current `main` baseline above.

P4-F **Integration & Workflow Hardening** is the active/final P4 implementation phase.
P4-D Saved ROI, Alpha Overlay/Flicker/Wipe, and arbitrary-angle Line Profile are
deferred and are not P4 completion blockers.

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
- P4-A Review Selection & Curation merged as PR #29 at
  `3486146494076e9b513843b90ec44e504043729e`.
- P4-B Comparison Set Persistence merged as PR #30 at
  `3a19589e6cbad5fa8c814c522df6a553f59ee340`.
- P4-C Session Persistence & Typed Recent merged as PR #31 at
  `436033a0d99513fe8db35f08305395127e430af2`.
- PR #32 Display Gain/Difference runtime stabilization merged at
  `e1ccf264f86e37b438c923faceae96c3ecb539b7`.
- PR #33 Difference/source-curation lifecycle merged at
  `51a540c92c372d71e02fd849fb5e0d406d0e9327`.
- P4-E Analysis Export Productivity merged as PR #34 at
  `79ee74134f1ebef9dd13f82e49f8e34407bb78f4`, the current inherited `main` baseline
  for P4-F.

The active plan is [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).
P4 is **Workflow & Session Productivity**. P4-F integration hardening is active and
closes P4 only after owner validation, independent review, and merge.

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
state is not persisted to Settings/QSettings or Session artifacts.

Pick membership is **not** source ownership, decode authority, residency protection,
preload authority, analysis working-set authority, Difference input authority, or
presentation-source authority. Split/Difference derived documents are not
independent pick identities.

PR #33 makes the source/derived Difference boundary explicit:

- native source tiles retain the interactive `Pick` control;
- a presented Difference tile shows a non-interactive/non-focusable `Derived` role
  and emits no Pick intent;
- Pick/Unpick/Clear Selection leave an active Difference unchanged because they are
  temporary workflow state only;
- **Keep Selection always closes any active Difference before Selected mutates**,
  regardless of whether the old A/B sources survive in the kept subset;
- active Difference presentation/binding/provenance is cleared and toolbar `Diff`
  becomes unchecked and disabled for the new workspace;
- Keep does not purge generation-keyed Difference Map Cache entries, bump source
  generations, or create curation-owned reload/residency/preload behavior;
- the next active Difference is established only by an explicit **Calculate** for a
  valid current-page Image 1/Image 2 pair;
- Calculate performs the existing generation-aware cache lookup first, reusing a
  hit without numerical-map recomputation or running the existing asynchronous
  calculation on a miss;
- after successful Calculate, toolbar `Diff` is visibility-only for that same active
  result and does not infer another pair or calculate implicitly.

Passive selection/page rerenders do not promote a cached map to active Difference
state. `DifferencePanel` remains the cache/numerical owner and MainWindow retains the
existing result presentation/restore paths.

## P4-B Comparison Set persistence — historical compatibility

P4-B introduced the first external `.pixelscope` v1 **Comparison Set** artifact with
`kind = "pixelscope-comparison-set"`. PR #30 is merged. P4-C supersedes new writes and
UI terminology with Session v1 but retains Comparison Set v1 read compatibility.

Comparison Set v1 persistent identity is a normalized **absolute local native-source
path**. It persists ordered logical Selected paths, optional selected Active,
optional applicable current-page Primary, stable layout, and minimum resolved RAW
profile metadata. It intentionally does not persist source arrays,
residency/LRU/protection, preload, Difference/cache, Display Gain, analysis state,
workers/tokens/generations, derived Split/Difference documents, ROI/Line, or temporary
P4-A Picks.

## P4-C PixelScope Session v1

P4-C generalizes new `.pixelscope` writes to `kind = "pixelscope-session"`, schema
version 1. The authoritative contract is
[`SESSION_CONTRACT.md`](SESSION_CONTRACT.md).

A Session persists durable user-authored workspace intent, not a process snapshot:

- Registered membership plus minimum resolved RAW reconstruction metadata;
- exact ordered Selected paths;
- one Selected source-path Current Comparison Page anchor;
- applicable source Active and Primary;
- stable layout mode;
- shared ROI and Line;
- Display Gain and applicable Split Channels state;
- a regenerable Difference recipe only when the saved A/B are both members of the
  saved Current Comparison Page.

Registered insertion order is not semantic Session state; Selected order is semantic.
Temporary Picks, decoded arrays, source residency/LRU/protection, previews, preload,
workers/tokens/generations, Difference maps/cache/results/generated documents,
calculated analysis results, and other reproducible runtime buffers are not saved.
Settings schema remains v5.

### Session Open transaction

Session Open reads/parses the artifact exactly once. It validates and probes paths
before decode, stages incoming registration identities before removing unrelated
current Registered sources, and leaves the existing workspace/Picks intact if zero
incoming sources actually register.

After the commit boundary it tears down any pre-existing active Difference through
the PR #33 lifecycle, clears temporary curation, restores loadable Selected in exact
saved order, reconstructs the saved page from the page anchor, establishes applicable
layout/Primary/source Active, and foreground-loads only the bounded Current Comparison
Page through the inherited MainWindow loader. It then restores Display Gain/Split,
ROI/Line, and applicable Difference intent. There is no Registered-wide eager decode.

Session restore exposes this asynchronous reconstruction through a MainWindow-owned
child overlay with a fixed eight-step procedure. It is an input shield/observer only:
no `QDialog`, no application-modal nested event loop, no Cancel/partial rollback
contract, and no source/selection/residency/worker/Difference authority.

### Session Difference contract

PR #32 remains generic runtime/concurrency/presentation authority and PR #33 remains
active Difference authority. Session does not pre-populate `_difference_source_ids`.
For an eligible recipe it restores exact compatible A/B/options on the reconstructed
Current Comparison Page and invokes one explicit **Calculate**. Only the normal PR
#33 result-ready path establishes active Difference provenance/document/toolbar
state.

Writer and reader eligibility are symmetric. PR #33 permits a hidden active
Difference binding to remain after page navigation while its A/B remain logically
Selected. If the user saves from a later page that no longer contains those A/B,
Session Save omits the stale/off-page Difference recipe. Reopen therefore never
creates special off-page Difference loading/residency ownership and never performs
an implicit calculation or pair/page substitution.

## Typed Recent entry

File entry UX is:

```text
Open Images...
Open Folder...
Open Session...
Open Recent Images      >
Open Recent Folders     >
Open Recent Sessions    >
--------------------------
Save Session...
```

Recent is a max-10 typed path-only MRU per Image, Folder, and Session. Image activation
delegates to the normal direct-image selection path; Folder activation delegates to
registration-only folder input; Session activation delegates to Session Open.
Missing paths use explicit **Remove / Keep**. Wrong-kind paths and existing invalid
Session artifacts remain history until explicitly removed. Recent bookkeeping is
best-effort observer metadata and cannot turn a successful canonical workflow into
failure.

Authoritative keys are `recent/images`, `recent/folders`, and `recent/sessions`;
legacy `recent/comparison_sets` is migration/read fallback only. Recent history is
outside ApplicationSettings schema v5 and Reset Settings and owns no source,
selection, curation, residency, preload, Difference, analysis, or page state.
Absolute paths may expose local filesystem layout.

## P4-E Analysis Export Productivity

P4-E consumes current result/presentation data without creating new numerical or
source authority. File menu retains **Export Statistics CSV...** and adds:

- **Export Histogram CSV...** for the exact current plotted Histogram series. Rows
  identify Full image/Active ROI scope and bounds, absolute source/series/channel,
  native bin edges/counts, current display edges, and current x/y modes. Ordering and
  numeric formatting are deterministic and locale-independent.
- **Export Line Profile CSV...** for the exact current plotted Line Profile series.
  Rows identify line coordinates, source/series/channel, current x/y modes, sample
  index/position, and current rendered value in deterministic order.
- **Export Difference Image...** for an explicitly established active Difference
  result only. PNG encodes the current Difference presentation preview, including
  current Absolute/Mask, threshold, Difference gain, and compatible channel state.
  It never screenshots UI chrome and never recalculates Difference.

The existing configured Export directory is reused. CSV serialization is small and
synchronous; Difference PNG encode/write reuses the existing bounded analysis worker
pool. Export does not reload source, promote residency, preload, bump source
validation generations, mutate Difference cache identity, or change
Selected/Active/Primary/Page. Cancel is a no-op; write failures provide compact status
feedback. Settings schema remains v5.

Saved/named/multiple ROI and Alpha Overlay are deferred. Session v1 already persists
current active ROI/Line intent; a named ROI manager still needs ownership/coordinate
semantics. Overlay/Flicker/Wipe UX has not demonstrated value beyond current Multi
View, synchronized navigation, and Difference.

## P4-F Integration & Workflow Hardening — Active

P4-F adds no new broad workflow or numerical semantics. It closes cross-feature gaps
between already-merged P4 subsystems while preserving the P2/P3 ownership hierarchy.
The focused implementation currently hardens two discovered integration contracts:

- Session Save writes the actual Current Comparison Page source anchor explicitly,
  so page persistence remains independent of source Active/Primary fallback state;
- production MainWindow close disarms that window's application-global Display Gain
  subscriptions and cancels outstanding viewer-local Gain preview work, preventing a
  later recreated window or Gain change from starting work in the closed window.

Focused P4-F regression coverage also composes Keep Selection → Difference teardown →
Session Save and Session restore → explicit Difference reconstruction → settled
Difference PNG export without recalculation or cache/generation mutation. Existing
P4-A/C/E and PR #32/#33 suites remain authoritative for subsystem semantics and are
not duplicated.

P4-F is not complete on this branch until owner Windows validation and independent
review are complete. P4 remains Active until P4-F merges; closure status and plan
archival are a docs-only follow-up after that merge.

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
Gain remains owned by its existing application-session state, and P4-A adds no
separate mode or contextual group.

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
- Difference uses the same header role width but shows `Derived` instead of an
  interactive Pick control.
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

PR #32 owns Display Gain worker/concurrency/presentation stabilization. P4-C persists
only the scalar Display Gain intent and reuses that existing runtime path during
restore. P4-F adds only window-lifetime disarming: closing one production MainWindow
unsubscribes its viewer/control callbacks from the application-global Display Gain
state and cancels viewer-local Gain preview work; the gain numerical/worker authority
is unchanged.

## Runtime/settings baseline

Settings schema remains version 5. P4-A adds no Settings/QSettings key and does not
persist the captured curation baseline or temporary Pick Set. Session is an explicit
external `.pixelscope` artifact and does not bump Settings schema. Typed Recent uses
separate QSettings path-history keys outside `SettingsRepository` ownership and Reset
Settings. P4-E reuses the existing configured Export directory and adds no schema.

Source residency remains exact native `source.nbytes` under P2 protected soft-budget
LRU semantics, with the P3-D large-selection refinement that **Selected alone is not
a protection owner**. Pick membership and Session metadata are also not protection
owners. The generic bounded protection authority is the Current Comparison Page plus
existing correctness dependencies. Selected/Picked-but-off-page resident sources may
therefore be evicted and normally reloaded when revisited.

Difference cache remains independent. Keep Selection always resets the active
Difference presentation/binding for the new Selected workspace but does not clear
generation-keyed cache entries or change source generations. Session never serializes
that cache or generated Difference result. P4-E Difference export consumes only the
current established presentation and does not touch numerical cache ownership.
Preload remains +1 Folder Position, max-one dedicated worker, with running-preload
promotion as established by P2. Session adds no Comparison Page speculative preload
or Registered-wide eager decode. P4-E adds no preload/residency path. Diagnostics
remain deterministic, bounded, sanitized, and observation-only.

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
3. P4-B — Comparison Set Persistence — Complete — PR #30
4. P4-C — Session Persistence & Typed Recent — Complete — PR #31 — `436033a0d99513fe8db35f08305395127e430af2`
5. P4-D — Saved ROI & Analysis Workspace Productivity — Deferred
6. P4-E — Analysis Export Productivity — Complete — PR #34 — `79ee74134f1ebef9dd13f82e49f8e34407bb78f4`
7. P4-F — Integration & Workflow Hardening — Active — owner validation/review pending

P4 inherits the P2/P3 ownership and numerical contracts above. Temporary workflow
state and export must not become source/cache/residency/analysis authority, and
Session persistence remains durable intent rather than process/runtime serialization.
P4-D Saved ROI and Alpha Overlay are not P4 completion blockers.

Arbitrary-angle Line Profile is intentionally omitted from P4. Because Line Profile
is an observation/sampling tool, a future arbitrary-angle version should define a
discrete sampling/pixel-path and coordinate-display contract explicitly rather than
implicitly introducing interpolation. The current utility does not justify that
semantic/UI complexity.
