# Execution plan: P4 — Workflow & Session Productivity

Status: Active — P4-A complete; P4-B implemented/focused validated, merge pending
Owner: repository owner + P4 orchestration agents
Last updated: 2026-08-11
Inherited merged baseline: P4-A / PR #29 merge commit
`3486146494076e9b513843b90ec44e504043729e`

## Goal

Build review/curation, reusable comparison sets, workflow entry, saved analysis
annotations, and focused viewer/export productivity on top of the stabilized P2/P3
image semantics and bounded Current Comparison Page architecture.

P4 must improve workflow without creating a second source, analysis, cache,
selection, or residency authority.

## Inherited P2/P3 baseline

The following ownership hierarchy is authoritative:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
Presented
    ↓
Resident when required
```

```text
Analysis Working Set = Current Comparison Page
```

Inherited invariants:

- Selected alone is not decoded-source residency authority.
- Current Comparison Page plus correctness dependencies remains the bounded generic
  source-protection authority.
- Comparison Page navigation creates no speculative preload.
- P2 preload remains Folder Position `+1`, exactly one position ahead, max-one
  speculative worker, with existing RUNNING promotion semantics.
- Display Gain is presentation-only and never redefines native analysis/request
  identity.
- Difference remains native code-domain for equal effective depth and independently
  normalized `[0,1]` for mixed effective depth.
- RAW Black/White metadata and display transforms do not enter Difference domain
  selection/normalization.
- temporary workflow state must not become source/cache/residency/analysis authority.
- Current Comparison Page is derived from Selected ordering/page offset and must not
  be serialized as an independently owned collection.

## Program sequence

`P4-0 → P4-A → P4-B → P4-C → P4-D → P4-E → P4-F`

| Order | Slice | Status |
|---|---|---|
| 0 | P4-0 P3 Closure & P4 Program Setup | Complete — PR #28 |
| 1 | P4-A Review Selection & Curation | Complete — PR #29 |
| 2 | P4-B Comparison Set Persistence | Implemented; focused owner validation PASS; merge pending — PR #30 |
| 3 | P4-C Comparison Set Entry UX & Recent Entries | Planned |
| 4 | P4-D Saved ROI & Analysis Workspace Productivity | Planned |
| 5 | P4-E Viewer Overlay & Export Productivity | Planned |
| 6 | P4-F Integration & Workflow Hardening | Planned |

Arbitrary-angle Line Profile is intentionally **not** a P4 slice. PixelScope's line
profile is an observation/sampling tool, so a future arbitrary-angle implementation
would require a deliberate discrete pixel-sampling/path and coordinate-display
contract rather than casually introducing interpolation. The expected utility does
not currently justify that semantic/UI cost.

## P4-0 — P3 Closure & P4 Program Setup — Complete

PR #28 merged at `e30c49d6759715228a820d673ad8939ea9a3afe8`.
The docs-only orchestration slice:

- recorded P3-E / PR #27 as merged and P3 as Complete;
- archived the completed P3 execution plan;
- established this P4 program plan;
- reconciled phase/status documentation;
- added no P4 runtime/UI state and changed no Settings/persistence schema.

## P4-A — Review Selection & Curation — Complete

### Goal

Allow a user to browse a large Selected set page by page, make temporary review
picks, then explicitly reduce Selected to the picked native images without changing
Files registration.

Authoritative flow:

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

### Implemented contract

P4-A merged as PR #29 at `3486146494076e9b513843b90ec44e504043729e`.

- There is **no explicit Review Select mode**. Eligible native source tiles in Multi
  View expose **Pick** directly; normal tile activation and navigation retain their
  inherited meanings.
- The first checked Pick captures the current ordered Selected IDs as the temporary
  baseline internally.
- `ReviewSelectionState` stores only baseline Selected IDs, picked native source
  IDs, and internal captured-baseline state. It stores no source/preview arrays,
  workers, caches, residency state, RAW-profile copies, or Current Comparison Page
  copy.
- The Pick text remains `Pick`. Checked membership uses the depressed/checked button
  state plus a bright-yellow tile-wide border; Active and Primary remain distinct.
- Picks remain marked while navigating across Comparison Pages. Off-page picks do
  not need to remain resident or protected.
- The presentation row exposes
  `Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection`.
  `Selected N` is the temporary Pick Set count, not the Files logical Selected count.
- **Clear Selection** clears only temporary picks.
- **Keep Selection** is disabled when the Pick Set is empty.
- Applying Keep Selection preserves original baseline Selected ordering among picked
  images rather than pick order.
- Non-picked images remain Registered in Files.
- Pick membership alone does not trigger decode, `_ensure_loaded()`, source LRU
  touch/protection, preload, foreground promotion, gained-preview generation,
  Difference calculation/cache changes, or analysis requests.
- Split/Difference derived presentation documents are not independent pick
  identities; picks refer to native registered/selected source document IDs.
- Only Keep Selection mutates logical Selected. Pick/Unpick/Clear Selection do not.
- There is no user-facing Cancel command.
- a different logical Selected-membership mutation invalidates the captured
  baseline/Pick Set before or with the existing normal selection mutation.
- registration-only folder input preserves the temporary curation state because it
  does not mutate Selected.
- P4-A Pick Set is not persisted across application/session restore.
- Settings schema remains v5.

### Implementation shape

- `core.review_selection.ReviewSelectionState` is the Qt-free ID-only state model;
  its `active` field is internal captured-baseline state rather than product mode.
- `ui.review_selection.ReviewSelectionController` owns temporary direct-curation
  orchestration and the `Selected N / Clear Selection / Keep Selection` controls.
- `TileHeader` exposes the stable source-tile Pick affordance separately from its
  existing Primary flag. The viewer `reviewPicked` property drives the tile-wide
  yellow selected border independently from Active styling.
- production application composition places Display Gain before the row stretch and
  then inserts the curation controls, producing the owner-approved unwrapped order
  without moving unrelated Main-toolbar commands.
- `DocumentListWidget` pre/post selection/removal signals allow curation invalidation
  without runtime PySide signal disconnect/reconnect rewiring; MainWindow retains
  normal selection/removal mutation authority.
- Keep Selection delegates the resulting ordered subset through the inherited
  Selected mutation/render/source lifecycle rather than creating a
  curation-specific source lifecycle.

### Focused coverage

Focused suites cover:

- state capture/exit, Pick/Unpick, duplicate idempotence, Clear, zero-pick,
  temporary lifetime, and baseline-order filtering;
- direct first-Pick capture, stable Pick checked/depressed state, picked count, and
  Active/Primary/Pick separation;
- bright-yellow tile-wide Pick state and cross-page restoration;
- `1 / 2 / 6 / 7 / 15 / 50` Selected cases;
- cross-page picks for 7 and 15 images;
- ordered Keep Selection result and non-picked registration retention;
- exact Files-tree subset and first-result Active state after Keep Selection;
- 50-image page-bounded loading/protection with no Pick-owned preload;
- no Pick/Unpick/Clear `_ensure_loaded`, render, Statistics, Difference-input, or
  Line Profile request churn and no source-generation/residency/Difference-cache
  change;
- pan / Ctrl+drag ROI / Shift+drag Line Profile gestures not toggling Pick;
- Split/Difference derived identity rejection;
- programmatic, production Files removal, direct signal fallback, and direct-Files
  Selected replacement invalidation.

## P4-B — Comparison Set Persistence — implemented, merge pending

### Goal and artifact boundary

P4-B adds a small explicit **Comparison Set** artifact instead of full application
session persistence. The extension is `.pixelscope`; v1 is JSON with
`kind = "pixelscope-comparison-set"` and `schema_version = 1`.

The persisted source identity contract is a normalized **absolute local source
path**. The v1 reader rejects blank/relative `sources[].path`, `active_path`, and
`primary_path` values before normalization. There is no relocation/fuzzy path
resolution. This makes v1 deterministic but machine/path-layout dependent and means
sharing the artifact can disclose local filesystem paths.

### Durable state

Persist only:

- ordered logical Selected native-source references;
- optional selected Active source;
- optional applicable Primary source;
- stable layout mode;
- minimum resolved RAW profile metadata needed to reconstruct a RAW source.

Save always serializes logical Selected rather than the temporary P4-A Pick Set. If
Picks exist but **Keep Selection** has not been applied, the original Selected set is
saved. After Keep, the curated Selected subset is saved. Save does not apply/clear
Picks, force RAW resolution, decode off-page members, or acquire Selected-wide
residency/protection.

### Open and transaction semantics

Open fully validates the artifact before logical workspace mutation. Loadable native
sources are registered through the normal path and replace Selected in saved order;
unrelated Registered sources remain. Saved Active determines the derived Current
Comparison Page, then an applicable page-local Primary and stable layout are
restored. Current Comparison Page/page index/page offset is derived and is never
serialized.

Missing paths partially load with a compact warning. Zero-loadable input leaves the
workspace unchanged. Corrupt JSON, wrong kind, future schema, invalid layout/path,
or invalid embedded RAW profile is rejected before registration/foreground loading.

Resolved RAW profile metadata is restored before foreground use. Unresolved RAW
remains unresolved and follows the inherited lazy foreground resolution path.

### Explicit non-ownership

Do **not** serialize or acquire ownership of:

- decoded `ImageDocument.source` arrays;
- source residency/LRU/protection state;
- Difference maps/cache;
- preload plans/workers or foreground-promotion state;
- active workers, request serials, generation/tokens;
- Display Gain state or gained preview buffers;
- Statistics/Histogram/Line Profile/Difference analysis request/result state;
- temporary Pick Set / captured curation baseline;
- transient Split/Difference presentation documents;
- Current Comparison Page as an independent duplicate collection;
- transient zoom/pan, ROI, or Line Profile state.

Comparison Sets are external artifacts and do not bump Settings schema v5.

### Validation status

The repository owner reports the focused P4-B Windows suite PASS:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\unit\test_comparison_set.py `
    tests\ui\test_p4b_comparison_set.py
```

Observed owner result: `36 passed`.

Independent review reports no remaining runtime/schema/test blocker. PR #30 remains
merge-pending for durable-doc consistency and normal final review/validation closure.

## P4-C — Comparison Set Entry UX & Recent Entries

Design one coherent workflow-entry surface that distinguishes at least:

- recent image entry;
- recent folder entry;
- recent Comparison Set entry.

Requirements:

- entry type must be explicit rather than inferred ambiguously from one flat list;
- history is bounded and deterministic;
- missing/moved path behavior is defined and non-destructive;
- privacy/path-retention implications are documented;
- opening a recent image/folder must reuse the P3 input intent contract rather than
  bypassing registration/selection semantics;
- opening a recent Comparison Set must use the P4-B Comparison Set loader, not ad-hoc
  state restoration;
- history must not own source residency or preload.

P4-C does not broaden P4-B into full persistent-session restoration.

## P4-D — Saved ROI & Analysis Workspace Productivity

Separate the **current active ROI** used by existing analysis from **saved ROI
definitions** used as reusable workflow annotations.

Before implementation define:

- image-space coordinate representation and bounds/clipping behavior;
- naming/ordering/selection rules;
- whether a saved ROI is global to a workflow artifact or associated with a specific
  source;
- behavior across different image dimensions;
- apply/activate/delete semantics;
- persistence boundary if/when saved ROI is intentionally added to a future schema.

Saved definitions must not become an alternative analysis working-set authority.
The active ROI applied to the current native analysis workflow remains the
numerical input.

## P4-E — Viewer Overlay & Export Productivity

### Alpha Overlay

Any Alpha Overlay must remain presentation-only. It may assist visual comparison
but must not mutate native source, Difference, Statistics, Histogram, Line Profile,
source generation, cache identity, residency accounting, or preload ownership.

Define source pairing, alignment/size compatibility, alpha control, active/primary
interaction, and teardown state before implementation.

### Export

Export work is intentionally limited to concrete review/analysis pain points. Do
not create a broad generic export framework in advance. For every exported artifact,
define whether it represents native data, normalized Difference data, a viewer
presentation, an ROI/plot result, or workflow metadata, and preserve the corresponding
numerical/domain semantics.

## P4-F — Integration & Workflow Hardening

Close P4 with cross-feature integration rather than adding another broad feature.
At minimum audit:

- P4-A curation with large Selected sets and page navigation;
- P4-B Comparison Set round-trip with RAW profile resolution, missing paths, and P2
  residency/preload reconstruction;
- P4-C recent-entry intent against image/folder/Comparison Set distinctions;
- P4-D saved ROI activation against Statistics/Histogram/Difference/Line Profile;
- P4-E presentation overlays/export against native-analysis and Difference domains;
- P2/P3 request identity, stale-result, source residency, Difference-cache, and
  preload invariants;
- Qt lifetime/focus/teardown at new production composition boundaries;
- durable docs, Windows owner characterization, and regression coverage.

No wall-clock performance threshold should become a merge gate without a separate,
evidence-backed performance requirement.

## P4-A explicit exclusions

P4-A does not add:

- Comparison Set serializer/loader or `.pixelscope` file format;
- Recent Images/Folders/Comparison Sets;
- Pick Set persistence or Settings schema changes;
- Saved ROI runtime/UI;
- arbitrary-angle Line Profile or interpolation/sampling redesign;
- Alpha Overlay or export behavior;
- source residency or preload policy/concurrency changes;
- Difference or Display Gain numerical changes;
- RAW Profile Library/CRUD/favorites/search, demosaic, white balance, CCM, or tone
  mapping;
- remote IQA/authentication or packaging/signing/installer behavior;
- broad MainWindow redesign.

## P4-B explicit exclusions

P4-B does not add full application/session persistence, Recent-entry history, Saved
ROI, arbitrary-angle Line Profile, Alpha Overlay/export workflows, source residency
or preload redesign, Difference/Display Gain numerical changes, RAW Profile Library
or processing, remote IQA/authentication, or packaging/release work.

## Validation policy

Runtime/UI slices use owner/local Windows validation. Chat implementation agents do
not bootstrap/search for a local Windows virtual environment or install dependencies.

P4-B focused validation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\unit\test_comparison_set.py `
    tests\ui\test_p4b_comparison_set.py
```

Owner-reported focused result: `36 passed`.

Before merge, run the standard repository contract as applicable:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Only observed results may be recorded as PASS. Docs-only closure commits do not
retroactively imply unobserved full-suite/tooling results.