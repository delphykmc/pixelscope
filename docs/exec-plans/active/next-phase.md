# Execution plan: P4 — Workflow & Session Productivity

Status: Active — P4-A implemented and owner-validated; durable-doc closure / merge pending
Owner: repository owner + P4 orchestration agents
Last updated: 2026-08-11
Inherited merged baseline: P4-0 / PR #28 merge commit
`e30c49d6759715228a820d673ad8939ea9a3afe8`

## Goal

Build review/curation, reusable comparison sessions, workflow entry, saved analysis
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
| 1 | P4-A Review Selection & Curation | Implemented and owner-validated; docs/merge pending |
| 2 | P4-B Persistent Comparison Sessions | Planned |
| 3 | P4-C Recent Entries & Session Entry UX | Planned |
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

## P4-A — Review Selection & Curation

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

P4-A is implemented on `feature/p4-a-review-selection-curation`. Owner/local Windows
runtime and requested validation are reported PASS. Independent re-review found the
previous runtime/test blockers resolved; durable-doc closure and merge remain.

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
- Initial P4-A Pick Set is not persisted across application/session restore.
- Settings schema remains v5 and no P4-B persistent-session behavior is introduced.

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

The owner reports requested local Windows validation PASS. Independent re-review
found no remaining runtime/test blocker; the remaining closure work is durable-doc
alignment and merge.

## P4-B — Persistent Comparison Sessions

Define the session schema only after separating durable user intent from runtime
implementation state.

Candidate durable state may include registered input references, ordered Selected,
current comparison/page position derivation inputs, layout/presentation choices,
applicable ROI/analysis/view state, and explicit feature state that has stable
product meaning.

Do **not** serialize runtime/derived/temporary ownership such as:

- decoded `ImageDocument.source` arrays;
- source residency/LRU/protection state;
- Difference or other caches;
- active workers, preload state, tokens, request serials, generations used only for
  stale-result authority;
- gained/derived preview buffers;
- temporary Pick Set / captured curation baseline;
- transient Split/Difference presentation documents;
- Current Comparison Page as an independent duplicate collection.

Session load must reconstruct runtime state through the normal registration,
selection, page, profile-resolution, load, and residency paths rather than reviving
internal worker/cache objects.

Versioning, missing-path behavior, portability/path semantics, atomic save/load,
corrupt/future-schema handling, and privacy implications must be explicit before
implementation.

## P4-C — Recent Entries & Session Entry UX

Design one coherent workflow-entry surface that distinguishes at least:

- recent image entry;
- recent folder entry;
- recent session entry.

Requirements:

- entry type must be explicit rather than inferred ambiguously from one flat list;
- history is bounded and deterministic;
- missing/moved path behavior is defined and non-destructive;
- privacy/path-retention implications are documented;
- opening a recent image/folder must reuse the P3 input intent contract rather than
  bypassing registration/selection semantics;
- opening a recent session must use the P4-B session loader, not ad-hoc state
  restoration;
- history must not own source residency or preload.

## P4-D — Saved ROI & Analysis Workspace Productivity

Separate the **current active ROI** used by existing analysis from **saved ROI
definitions** used as reusable workflow annotations.

Before implementation define:

- image-space coordinate representation and bounds/clipping behavior;
- naming/ordering/selection rules;
- whether a saved ROI is global to a session or associated with a specific source;
- behavior across different image dimensions;
- apply/activate/delete semantics;
- session persistence boundary once P4-B exists.

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
presentation, an ROI/plot result, or session metadata, and preserve the corresponding
numerical/domain semantics.

## P4-F — Integration & Workflow Hardening

Close P4 with cross-feature integration rather than adding another broad feature.
At minimum audit:

- P4-A curation with large Selected sets and page navigation;
- P4-B session round-trip with RAW profile resolution, missing paths, and P2
  residency/preload reconstruction;
- P4-C recent-entry intent against image/folder/session distinctions;
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

- persistent comparison session serializer/loader or session file format;
- Recent Images/Folders/Sessions;
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

## P4-A validation policy

P4-A changes runtime/UI/source integration, so the P4-0 docs-only validation
exception does not apply. The Chat implementation agent does not bootstrap/search
for a local Windows virtual environment or install dependencies.

Run focused tests first:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_review_selection.py tests\ui\test_p4a_review_selection.py tests\ui\test_p4a_review_selection_review_fixes.py
```

Then run the full owner/local contract:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Historical implementation-agent evidence was limited to a scratch syntax compile
of changed Python drafts and the Qt-free state-model test reporting `3 passed`;
PySide6 was unavailable in that scratch environment. The repository owner later
reported the requested local Windows validation PASS on the runtime/test
implementation. The current closure changes are docs-only, so applicable docs/diff
checks still need to be observed before merge; no new unobserved PASS is inferred.