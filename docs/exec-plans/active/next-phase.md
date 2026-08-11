# Execution plan: P4 — Workflow Productivity

Status: Active — P4-B Comparison Set Persistence implementation/validation
Owner: repository owner + P4 orchestration/implementation agents
Last updated: 2026-08-11
Inherited merged baseline: P4-A / PR #29 merge commit
`3486146494076e9b513843b90ec44e504043729e`

## Goal

Improve large-selection review and repeatable comparison workflows without creating a
second source, selection, analysis, cache, residency, or preload authority.

Authoritative runtime hierarchy:

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

`Analysis Working Set = Current Comparison Page`.

## Program sequence

| Order | Slice | Status |
|---|---|---|
| 0 | P4-0 P3 Closure & P4 Program Setup | Complete — PR #28 |
| 1 | P4-A Review Selection & Curation | Complete — PR #29 |
| 2 | P4-B Comparison Set Persistence | Active |
| 3 | P4-C Recent Entries & Comparison Set Entry UX | Planned |
| 4 | P4-D Saved ROI & Analysis Workspace Productivity | Planned |
| 5 | P4-E Viewer Overlay & Export Productivity | Planned |
| 6 | P4-F Integration & Workflow Hardening | Planned |

P4-B and P4-C are sequential but solve different ownership problems:

```text
P4-B: What durable comparison data is saved and how is it reopened?
P4-C: What entry did the user recently open and how is it entered again quickly?
```

P4-C runtime work must not begin until P4-B is merged and latest main is rechecked.

## P4-A — Review Selection & Curation — Complete

PR #29 merged at `3486146494076e9b513843b90ec44e504043729e`.

P4-A provides a temporary page-spanning Pick Set over logical Selected. The first Pick
captures the Selected baseline. **Keep Selection** replaces logical Selected with the
picked subset in baseline order. Pick state is ID-only, temporary, and never owns
source residency, preload, cache, decode, or numerical analysis.

## P4-B — Comparison Set Persistence — Active

Branch: `feature/p4-b-comparison-set-persistence`
Recommended PR title: `[ChatGPT-assisted] Add comparison set persistence`

### Product boundary

P4-B is **not** full application-session persistence. It stores a reusable ordered
logical comparison set plus the minimum stable context needed to continue comparing.

Versioned artifact:

```text
*.pixelscope
kind = pixelscope-comparison-set
schema_version = 1
```

Persisted v1 payload:

```text
ordered logical Selected source references
optional Active source reference
optional Primary source reference
layout mode: Auto | Single View | Multi View
resolved RawProfile payload only when already deterministically available
```

Persistent identity is normalized absolute local source path. Runtime document IDs
are never serialized.

### Non-persisted state

Do not serialize:

- Registered non-Selected catalog members;
- Current Comparison Page or page_start;
- native decoded arrays or previews;
- Difference cache, source residency/LRU/protection;
- preload state, workers, load/preload tokens, request/generation serials;
- P4-A Pick Set/captured baseline;
- Split/Difference derived documents;
- ROI/Line/Saved ROI/Plots state;
- Display Gain;
- window/dock/splitter geometry inside the artifact;
- Recent history or diagnostics.

### Save contract

- Save current logical Selected in exact ordering.
- Never substitute the temporary P4-A Pick Set.
- A curated subset is saved only after **Keep Selection** changes logical Selected.
- Saving must not clear Pick state, decode off-page sources, or promote Selected-wide
  residency/protection.
- Use atomic same-directory temporary write + replacement.
- Empty Selected is a normal no-op UX.

### Open contract

Validate artifact syntax/schema completely before mutating workspace state.
Then:

```text
loadable saved source refs
        ↓ existing normal registration/reuse
logical Selected in saved order
        ↓
restore saved Active when loadable, otherwise first loadable
        ↓
derive Current Comparison Page from Active position
        ↓
restore applicable Primary through existing page-local path
        ↓
restore stable layout mode
```

Existing Registered catalog is retained. Saved sources already Registered reuse their
current runtime identity. New saved sources use normal registration without eager RAW
profile dialog/decode.

A saved resolved RAW profile is validated and associated before foreground selection.
An unresolved RAW stores only its source path and follows the inherited lazy foreground
profile-resolution contract when native source is actually required.

Opening a set must call the inherited Selected mutation path so P4-A temporary
curation invalidation is inherited rather than reimplemented.

Missing source paths are normal: load valid members in saved order and report missing
members compactly. If no member is loadable, leave current workspace unchanged.
Malformed/wrong-kind/future-schema/invalid-field artifacts are rejected before any
workspace mutation.

### Path/privacy policy

v1 is a deterministic local workflow:

- normalized absolute paths;
- no fuzzy relocation;
- no filename-only/size-only match;
- no recursive moved-file search;
- no automatic repair.

The artifact therefore contains potentially sensitive local path metadata; document
that clearly in user-facing guidance.

### Architecture shape

```text
Qt-free ComparisonSet domain/schema
        ↓
ComparisonSetRepository codec + atomic storage
        ↓
ComparisonSetController user command orchestration
        ↓
existing registration / Selected / Active / Primary / layout paths
```

The repository/controller does not become a source owner and does not introduce a new
worker pool.

### P2/P3 invariants

- Selected/Comparison Set membership is not residency protection authority.
- Opening a large set must not eager-decode all members.
- source residency remains exact native `source.nbytes`.
- Difference cache remains independent.
- Folder Position preload remains `+1`, one position, max-one speculative worker.
- Comparison Page navigation creates no preload.
- Difference, Display Gain, RAW Black/White, Statistics, Histogram, Line Profile, and
  Split semantics remain unchanged.
- Settings schema remains v5. Comparison Set is an external user artifact, separate
  from ApplicationSettings and workspace QSettings.

### Required P4-B coverage

Qt-free domain/repository tests:

- v1 round trip and ordered sources;
- duplicate rejection;
- path normalization;
- malformed/wrong-kind/empty/future-schema/field-type validation;
- Active/Primary optional identities and layout validation;
- resolved RAW profile round trip and unresolved representation;
- explicit same-version unknown-field policy;
- atomic-save result validity.

Runtime/UI tests:

- save logical Selected rather than Pick Set;
- Keep Selection result is saveable;
- save does not clear Pick state;
- exact order, Active, derived page, applicable Primary, layout restore;
- pre-existing non-set Registered documents retained;
- corrupt/zero-loadable leaves workspace unchanged;
- partial missing loads valid ordered subset;
- open invalidates P4-A curation only through inherited Selected mutation;
- large set remains page-bounded for foreground load/protection;
- resolved RAW profile is reused; unresolved RAW remains lazy;
- no Split/Difference derived identity persistence.

### Owner-local validation

Focused first:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_comparison_set.py tests\ui\test_p4b_comparison_set.py
```

Then full contract because runtime/source/tests changed:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The implementation agent must not claim owner-local PASS until the owner reports it.

## P4-C — Recent Entries & Comparison Set Entry UX — Planned

P4-C begins only after P4-B merge and a fresh latest-main/runtime/docs audit.

Planned model:

```text
RecentEntryKind
├─ image
├─ folder
└─ comparison_set
```

Recommended history policy: max 15 total, MRU ordering, identity = kind + normalized
path, duplicate reopen moves to front. History is a separate bounded repository; it
is not ApplicationSettings schema and must not bump settings v5.

Recent actions reuse existing workflows rather than reconstructing them:

- Recent Image → Open Images intent: register + select;
- Recent Folder → Open Folder intent: register only;
- Recent Comparison Set → P4-B loader.

Successful user-facing entry workflows create history. Internal source reload,
residency reload, preload, and worker completion do not. A clicked missing entry warns,
removes that stale history entry deterministically, and leaves workspace unchanged.

Recent history is path metadata only: bounded, clearable, not telemetry, not diagnostics
payload, not source/residency/preload/Registered/Selected authority.

## Later P4 slices

P4-D Saved ROI, P4-E Viewer Overlay & Export, and P4-F integration remain planned.
A full persistent application session is deferred/future scope rather than an implicit
extension of P4-B Comparison Set v1.
