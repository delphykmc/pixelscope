# Execution plan: P4 — Workflow & Session Productivity

Status: Active — P4-A implemented; owner validation / independent review / merge pending
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
| 1 | P4-A Review Selection & Curation | Implemented; validation/review/merge pending |
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
temporary Review Pick Set
    ↓ Keep Picked
new Selected subset
```

### Implemented contract

P4-A is implemented on `feature/p4-a-review-selection-curation`; owner/local Windows
validation, independent review, and merge are pending.

- **Review Select** is an explicit mode, never an implicit side effect of normal
  tile activation or navigation.
- `ReviewSelectionState` stores only baseline Selected IDs, picked native source
  IDs, and active state. It stores no source/preview arrays, workers, caches,
  residency state, RAW-profile copies, or Current Comparison Page copy.
- native source tiles expose a separate **Pick / Picked** check affordance only while
  review mode is active.
- Picks remain marked while navigating across Comparison Pages. Off-page picks do
  not need to remain resident or protected.
- `Keep Picked` is disabled when the Pick Set is empty.
- Applying `Keep Picked` preserves original baseline Selected ordering among picked
  images rather than pick order.
- Non-picked images remain Registered in Files.
- Picked membership alone does not trigger decode, `_ensure_loaded()`, source LRU
  touch/protection, preload, foreground promotion, gained-preview generation,
  Difference calculation/cache changes, or analysis requests.
- **Active**, **Primary**, and **Picked** are distinct states and affordances.
- Split/Difference derived presentation documents are not independent pick
  identities; picks refer to native registered/selected source document IDs.
- Only `Keep Picked` mutates Selected. Pick/Unpick/Clear Picks do not.
- **Cancel** clears the temporary baseline/Pick Set without changing Selected,
  Current Comparison Page, Active, or Primary.
- a different Selected-membership mutation invalidates the temporary review state
  before the existing normal selection mutation proceeds.
- Initial P4-A Pick Set is not persisted across application/session restore.
- Settings schema remains v5 and no P4-B persistent-session behavior is introduced.

### Implementation shape

- `core.review_selection.ReviewSelectionState` is the Qt-free ID-only state model.
- `ui.review_selection.ReviewSelectionController` owns temporary workflow
  orchestration and the contextual control group.
- `TileHeader` exposes the explicit source-tile Pick/Picked affordance separately
  from its existing Primary flag.
- production application composition installs the Review controller without moving
  Layout, Comparison Page, Display Gain, or unrelated Main-toolbar commands.
- Keep Picked delegates the resulting ordered subset through the inherited Selected
  mutation/render/source lifecycle rather than creating a curation-specific source
  lifecycle.

### Focused coverage

New focused suites cover:

- state enter/exit, Pick/Unpick, duplicate idempotence, Clear, zero-pick, temporary
  lifetime, and baseline-order filtering;
- inactive tile behavior, explicit active-mode Pick affordance, picked count,
  Keep/Clear/Cancel state, and Active/Primary/Picked separation;
- `1 / 2 / 6 / 7 / 15 / 50` Selected cases;
- cross-page picks for 7 and 15 images;
- ordered Keep Picked result and non-picked registration retention;
- 50-image page-bounded loading/protection with no Pick-owned preload;
- no Pick/Unpick `_ensure_loaded`, render, Statistics, Difference-input, or Line
  Profile request churn and no source-generation/residency/Difference-cache change;
- Split/Difference derived identity rejection;
- programmatic and direct-Files Selected replacement invalidation.

Owner/local Windows focused/full validation remains required before merge.

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
- temporary Review Pick Set;
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
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_review_selection.py tests\ui\test_p4a_review_selection.py
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

Implementation-agent evidence is limited to a scratch syntax compile of the changed
Python drafts and the Qt-free state-model module test reporting `3 passed`. PySide6
was unavailable in that scratch environment, so focused UI tests and the repository
full validation above were **not run by the implementation agent; owner/local
Windows validation is required**.
