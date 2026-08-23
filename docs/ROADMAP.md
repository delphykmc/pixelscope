# Roadmap

## Delivered baseline

### P0/P1 — Product foundation — Complete

PixelScope provides local image registration/selection, synchronized one-to-six-image
comparison, Statistics, Histogram, Line Profile, Difference, Split Channels, RAW
loading, fixed comparison layouts, and stable viewer/navigation behavior.

P1-D/P1-E/P1-F workspace polish completed as PR #10–#12.
Historical plan:
[`docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md).

### P2 — Runtime Foundation, Settings & Performance — Complete

Completed sequence:

`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`

P2 established typed settings, independent Difference/source budgets, byte-budgeted
source residency, bounded protection, one-position Folder preload, RUNNING preload
promotion, runtime diagnostics, and bounded application-worker ownership.

P2-F merged as PR #20 at
`9c66629f6392971b8c52ac9dff27b16166cf9829`.
Historical plan:
[`docs/exec-plans/completed/p2-runtime-foundation-settings-performance.md`](exec-plans/completed/p2-runtime-foundation-settings-performance.md).

### P3 — Image Semantics & RAW Processing — Complete

P3 established the authoritative local hierarchy:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page        # max 6
    ↓
Presented
    ↓
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

P3 also fixed Gray/mixed-bit Difference semantics, native RAW authority, Display Gain,
large logical Selected sets, unified input, and lazy RAW profile resolution.

P3 completed with PR #27 at
`835634a58609601605fd0fc18a3028b64225f535`.
Historical plan:
[`docs/exec-plans/completed/p3-image-semantics-raw-input.md`](exec-plans/completed/p3-image-semantics-raw-input.md).

### P4 — Workflow & Session Productivity — Complete

P4 delivered temporary Pick/Keep curation, Comparison Set compatibility, Session v1,
typed Recent Images/Folders/Sessions, Difference/source-curation lifecycle alignment,
focused analysis export, and workflow hardening.

P4-F merged as PR #35 at
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`.
Completed plan:
[`docs/exec-plans/completed/p4-workflow-session-productivity.md`](exec-plans/completed/p4-workflow-session-productivity.md).

Deferred from P4:

- saved/named/multiple ROI management;
- Alpha Overlay / Flicker / Wipe;
- arbitrary-angle Line Profile with an explicit sampling contract.

## Forward sequence

```text
P5 Remote IQA Platform
    ↓
P6 Identity, Access & Remote Operations
    ↓
P7 Release Engineering & Distribution
```

Active execution plan:
[`docs/exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

P5 durable contract:
[`docs/REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Current schema-v2 result contract:
[`docs/REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).

P5-D implementation contract:
[`docs/P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md).

Historical schema-v1 compatibility contract:
[`docs/REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).

# P5 — Remote IQA Platform — Active

## Product objective

P5 connects PixelScope's fast local inspection workflow to an external GPU IQA
service without redefining local source ownership.

```text
fast local inspection
    ↓ optional remote evaluation
submit Current Pair or deterministic Folder Pair
    ↓
non-modal remote job
    ↓
continue local work
    ↓
explicit Open Result
    ↓
Absolute / Relative Dataset Overview
    ↓
Scene Trend / outliers
    ↓
explicit Inspect in Viewer
    ↓
native Scene sources + spatial grid inspection
    ↓
explicit Return to captured local comparison
```

Remote IQA remains feature-local. It does not extend
`Registered → Selected → Current Comparison Page → Presented → Resident` with another
source owner.

## Numerical/result authority — schema v2

P5-A/schema v1 remains historical read-only compatibility. P5-A2 moved the durable
numerical model to source-oriented schema v2:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 separates `variant_id`, `source_id`, `scene_id`, and
`measurement_context_id` and stores server-authored W/S1/S2/count/valid source
measurements. PixelScope locally derives selected target/reference comparisons.

Schema-v2 source bindings may additionally carry optional `storage_root_id` location
metadata. It does not change immutable source identity or `measurement_context_id`;
old v2 artifacts that omit it remain result-readable but cannot use native P5-D Inspect
without an explicit portable root locator.

Key defaults remain:

- absolute Dataset Overview = `pooled_weighted_mean`;
- relative Dataset Overview = arithmetic mean of valid Scene comparison values;
- power mode 1 = ratio of pair-valid aggregate weighted means;
- power mode 2 = arithmetic mean of finite pair-valid grid log-ratios;
- signed attributes = pair-valid weighted target minus reference;
- v1 = explicit read-only compatibility with no synthetic v1→v2 upgrade.

Every published successful Scene binds every declared variant exactly once and obeys
the same geometry/numerical invariants whether the enclosing result is COMPLETE or
PARTIAL. Multiple variant bindings may intentionally reference one concrete
`source_id`; native source identity is not duplicated merely to fill variant slots.

## P5 execution sequence

```text
P5-0
→ P5-A schema v1
→ P5-A2 schema v2
→ P5-B local result workspace
→ P5-C submission/shared storage
→ P5-D viewer-linked inspection
→ P5-E historical result workflow
→ P5-F integration/performance hardening
→ P5 Complete
```

| Order | Slice | Status |
|---|---|---|
| 0 | P5-0 P4 Closure & P5 Program Setup | Complete — PR #36 |
| 1 | P5-A Contract Fixtures & IQA Domain / schema v1 | Complete — PR #37 |
| 2 | P5-A2 Schema-v2 durable + executable migration | Complete — PR #39 + #40 |
| 3 | P5-B IQA Workspace & Local Result Exploration | Complete — PR #38 |
| 4 | P5-C Submission & Shared Storage | **Complete — PR #42** |
| 5 | P5-D Viewer-linked Scene Inspection | **Active — Draft PR #43 review closeout** |
| 6 | P5-E Historical Result Workflow | Planned |
| 7 | P5-F Integration & Performance Hardening | Planned |

## P5-0 / P5-A / P5-A2 — Complete

- P5-0 / PR #36 established the program and ownership boundaries.
- P5-A / PR #37 is the historical executable schema-v1 baseline.
- P5-A2 Stage 1 / PR #39 froze the schema-v2 source-oriented numerical contract.
- P5-A2 Stage 2 / PR #40 implemented the schema-v2 reader, artifacts, math, geometry,
  deterministic fixtures, and v1 dispatch.

## P5-B — IQA Workspace & Local Result Exploration — Complete

PR #38 merged at `a44978db783ebcecb0d55f8abb52b583e0fdc47c`.

Delivered the canonical Results UI/controller used by later slices:

- **File > Open IQA Result...** version dispatch;
- summary-first schema-v2 Absolute default;
- N-way Reference switching and canonical relative math;
- bounded deferred Scene-grid access;
- Overview, Scene Trend, partial-result diagnostics, and source identity cards;
- Plots-equivalent IQA dock behavior;
- passive result browsing that does not mutate the local image workspace;
- v1 historical read-only compatibility.

## P5-C — Submission & Shared Storage — Complete

PR #42 merged as `main@24b328d02c0cd56fb79920e069af06d6e4cb706f`.

P5-C delivered:

- Settings schema v6 Remote IQA endpoint and machine-local logical storage mappings;
- portable `storage_root_id + relative_path` identity;
- deterministic two-variant Current Pair / Folder Pair submission;
- SHA-256 source identity and content-addressed staging;
- containment and concurrent-publication hardening;
- one-shot create, bounded polling/result-reference recovery, cancellation and stale
  result-mapping protection;
- schema-v2 COMPLETE/PARTIAL result handling through the P5-B reader/workspace;
- Request Inspector, Replay JSON, deterministic result fixtures, and localhost fault
  harnesses;
- production-composition regressions proving remote preparation does not become local
  Files/Selected/current-page/residency/preload authority.

The PR closeout records independent latest-head review PASS and owner final full
repository validation PASS. Those results are historical P5-C evidence and are not
carried forward as P5-D validation.

## P5-D — Viewer-linked Scene Inspection — Active

### Goal

Turn an explicitly chosen schema-v2 Scene into a temporary native PixelScope inspection
without creating another source/viewer/residency authority and without making passive
Results browsing mutate local comparison state.

### Current implementation

- Results remain passive until **Inspect in Viewer** is invoked.
- Active P4-A temporary Picks block initial Inspect rather than being silently
  discarded.
- Source bindings may carry optional `storage_root_id`; old schema-v2 artifacts that
  omit it still open normally but native Inspect is unavailable for those sources.
- `storage_root_id` is location metadata only. It does not change source equality,
  `measurement_context_id`, or schema version 2.
- Every required Scene binding is resolved through the P5-C logical-root authority and
  uses the same P5-C ordinary-image header probe/format acceptance.
- Every unique native source is decoded from one encoded byte buffer; SHA-256 over that
  exact buffer must match the published source before any local mutation. The exact
  decoded object carrying that SHA becomes the committed local source generation.
- Verification is all-or-nothing. Missing/moved/remapped/hash/dimension/decode failures
  do not produce a partial native comparison.
- Multiple variant bindings may share one `source_id`; P5-D retains those IQA aliases
  while using one canonical Files/native-source document. Distinct source identities
  may not claim one physical locator.
- A Scene with more than six variant bindings is not silently truncated; native Inspect
  is unavailable while result browsing remains available.
- Successful Inspect reuses/registers canonical Files paths first, advances canonical
  load tokens, and publishes every exact verified decoded generation into the normal
  document/residency owner **before** any Selected/render transition. Only after all
  unique sources hold those verified generations does the canonical
  Selected/current-page workflow present them; normal eviction enforcement follows
  after current-page protection exists.
- Replacing stale resident or previously evicted bytes advances source generation and
  invalidates dependent source-view caches while retaining the canonical document ID.
- When multiple variant bindings share one native source, a bounded
  **Shared-source spatial binding** selector keeps each aliased `variant_id` reachable
  by overlay and Block Inspector without duplicating Files/native identity.
- First successful Inspect captures one transient Return snapshot containing Selected
  order, Comparison Page anchor, applicable Active/Primary, and layout.
- Linked Scene changes replace the inspected Scene while retaining the first Return
  snapshot.
- Newer local Selected/Files/layout/Primary intent invalidates Return rather than
  allowing old IQA state to overwrite newer user intent.
- A new P4-A Pick started after Inspect is preserved and invalidates Return; P5-D never
  clears that newer curation state to restore an older snapshot.
- Live Remote IQA root-mapping changes increment the P5-D locator revision, cancel/drop
  verification started under older settings, and refresh Inspect availability.
- Return explicitly restores the captured page and actual Single/Multi-view Active
  presentation where still applicable.
- IQA Reference and local Primary remain independent identities.
- Spatial values reuse schema-v2 W/S1/S2/count/valid and canonical power-ratio math:
  Absolute = per-cell `S1/W`; Relative power = raw target/reference dB; signed = raw
  target-reference delta.
- Existing schema-v2 geometry maps analysis-grid cells to source/viewer coordinates;
  non-zero origins, non-integer affine transforms, valid rectangles, and discarded
  borders share one draw/hit-test convention.
- Overlay rendering is vector/block based on the existing `ImageViewer` ViewBox; no
  full-resolution overlay bitmap, source registry, viewer stack, or residency owner is
  introduced.
- Block Inspector exposes row/column, validity, W/S1/S2/count, mean, Reference/pair
  state, analysis bounds, and mapped source polygon. Invalid cells remain invalid.
- Inspect/grid workers use generation/result/Scene/local-intent/settings/spatial-request
  identity and reject stale callbacks; new Result open and shutdown cancel active
  feature-local work.

Detailed contract and manual-validation matrix:
[`docs/P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md).

### P5-D remaining gates

P5-D is **not Complete** until all of the following are observed on the exact review
head:

1. focused reviewer-closeout plus existing P5-D unit/UI regressions pass;
2. repository Ruff check and formatter check pass;
3. `mypy src`, docs checker, `pip check`, and diff check pass;
4. owner Windows manual validation covers exact decoded source identity, stale resident
   replacement, repeated-source variant aliases including active spatial alias
   switching, source mapping/hash failures, Inspect/Return/Pick behavior, root-remap
   stale-drop, linked Scene navigation, Reference/Primary independence, spatial
   alignment, Difference/Gain/ROI/Line interaction, and close/recreate behavior;
5. independent whole-PR latest-head review finds no merge blocker;
6. owner approves merge.

No P5-D PASS is inferred from the P5-C validation record or an older P5-D head.

## P5-E — Historical Result Workflow — Planned

Extend the canonical result-open path with:

- bounded Recent IQA Results;
- production logical-root reopen;
- immutable result/source-hash identity diagnostics;
- result-only mode when sources are unavailable;
- provenance display;
- explicit v1 historical handling.

Session v1 is unchanged. Any future Session-carried IQA reference requires an explicit
new Session schema/version decision.

## P5-F — Integration & Performance Hardening — Planned

Validate the composed workflow against the real external service and realistic data:

- actual server adapter/protocol compatibility;
- SMB/network bandwidth and grid-loading behavior;
- bounded grid cache/preload tuning;
- reference-switch and native Inspect latency;
- batch/job stress and failure/cancellation cases;
- stale callbacks and close/recreate safety;
- proof remote batch membership does not become local source/residency authority;
- optional detail artifact characterization;
- P5 closure documentation.

No fixed wall-clock number is a correctness gate. Correctness gates remain stable
versioned identity/math/geometry, bounded ownership, no duplicate work, stale-result
rejection, and teardown safety.

# P6 — Identity, Access & Remote Operations — Planned

- Login / SSO;
- token and credential lifecycle;
- permission/access policy;
- audit integration;
- operational administration and controlled result cleanup.

# P7 — Release Engineering & Distribution — Planned

- exactly PyInstaller 5.7 `onedir`;
- portable ZIP;
- Inno Setup;
- clean-PC smoke testing;
- signing;
- update strategy;
- repeatable release process.

## Deferred optimization outside the phase sequence

Schedule only when profiling/user-visible latency demonstrates need:

- broader source preload policy changes;
- CPU/I/O aggressiveness controls;
- broader resource Settings exposure;
- process profiler telemetry;
- native/SIMD Display Gain optimization;
- eager/full download of 2K IQA detail maps;
- WebSocket progress if polling proves insufficient.
