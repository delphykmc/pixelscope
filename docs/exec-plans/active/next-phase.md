# Execution plan: P4 — Workflow & Session Productivity

Status: Active — P4-0 program setup / P4-A design next
Owner: repository owner + P4 orchestration agents
Last updated: 2026-08-11
Inherited merged baseline: P3-E / PR #27 merge commit
`835634a58609601605fd0fc18a3028b64225f535`

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
- temporary workflow state must not become source/cache/residency authority.
- Current Comparison Page is derived from Selected ordering/page offset and must not
  be serialized as an independently owned collection.

## Program sequence

`P4-0 → P4-A → P4-B → P4-C → P4-D → P4-E → P4-F`

| Order | Slice | Status |
|---|---|---|
| 0 | P4-0 P3 Closure & P4 Program Setup | Active |
| 1 | P4-A Review Selection & Curation | Design next |
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

## P4-0 — P3 Closure & P4 Program Setup

Docs-only orchestration slice:

- record P3-E / PR #27 as merged and P3 as Complete;
- archive the completed P3 execution plan;
- replace the active plan with this P4 program;
- reconcile stale phase/status documentation only;
- do not implement P4 runtime/UI state or change Settings/persistence schemas.

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
    ↓ Apply
new Selected subset
```

### Required contract

- **Review Select** is an explicit mode, never an implicit side effect of normal
  selection/navigation.
- Pick Set is temporary workflow state.
- Picks remain marked while navigating across Comparison Pages.
- `Keep Picked` is disabled when the Pick Set is empty.
- Applying `Keep Picked` preserves original Selected ordering among picked images.
- Non-picked images remain Registered in Files.
- Picked membership alone must not trigger decode, preload, residency protection,
  foreground loading, Difference calculation, or analysis requests.
- **Active**, **Primary**, and **Picked** are distinct states and affordances.
- Split/Difference derived presentation documents are not independent pick
  identities; picks refer to native registered/selected source documents.
- Only `Keep Picked` mutates Selected. Pick/Unpick/Clear Picks must not do so.
- Initial P4-A Pick Set is not persisted across application/session restore.
- Applying the subset must leave the resulting selection/page/active state
  deterministic and compatible with the inherited Current Comparison Page model.

### Validation direction

Tests should cover zero/one/many picks, cross-page persistence, original-order
preservation, non-picked registration retention, no pick-owned decode/residency,
Active/Primary/Picked separation, derived-presentation identity rejection, and
apply behavior on large selections.

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

## Explicit exclusions for P4-0

P4-0 implements none of the runtime/UI slices above. It does not add:

- Review Select / Pick / Unpick / Keep Picked;
- session serializer/loader;
- Recent Files/Folders/Sessions;
- Saved ROI runtime/UI;
- arbitrary-angle Line Profile;
- Alpha Overlay;
- export behavior;
- Settings schema/persistence changes;
- source residency/preload changes;
- Difference/Display Gain/RAW profile workflow changes;
- runtime source/test changes.

## P4-0 validation policy

P4-0 is docs-only. The Chat implementation agent does not bootstrap/search for a
local Windows virtual environment or install dependencies.

Applicable owner/local checks:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_docs_contract.py
git diff --check
```

Full pytest, Ruff, Ruff format, mypy, and `pip check` are not re-required solely for
this docs-only transition. If a source/test/config file enters the diff, that
exception no longer applies.
