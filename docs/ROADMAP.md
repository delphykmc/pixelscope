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
P5 Remote IQA Platform complete through P5-F
    ↓
R Repository Refactoring & Validation Hardening
    ↓
P5-G External GPU/SMB Validation & Closeout when environment is available
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

P5-D completed implementation contract:
[`docs/P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md).

P5-E historical-result contract:
[`docs/P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

P5-F integration characterization:
[`docs/P5F_INTEGRATION_CHARACTERIZATION.md`](P5F_INTEGRATION_CHARACTERIZATION.md).

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
explicit Open Result / historical reopen
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
→ P5-F repository-side integration/performance hardening
→ P5-G external GPU/SMB validation & closeout
→ P5 Complete
```

| Order | Slice | Status |
|---|---|---|
| 0 | P5-0 P4 Closure & P5 Program Setup | Complete — PR #36 |
| 1 | P5-A Contract Fixtures & IQA Domain / schema v1 | Complete — PR #37 |
| 2 | P5-A2 Schema-v2 durable + executable migration | Complete — PR #39 + #40 |
| 3 | P5-B IQA Workspace & Local Result Exploration | Complete — PR #38 |
| 4 | P5-C Submission & Shared Storage | **Complete — PR #42** |
| 5 | P5-D Viewer-linked Scene Inspection | **Complete — PR #43 · `b086443d188eb9daae4bbf4f0faab3ff1d114f93`** |
| 6 | P5-E Historical Result Workflow | **Complete — PR #44 · `6a0a334d61a7495b9c3433edfcbd537c8df59468`** |
| 7 | P5-F Integration & Performance Hardening | **Complete — PR #45 · `6634447fc3c48545a2482718dd3f444928806218`** |
| 8 | P5-G External GPU/SMB Validation & Closeout | **Deferred — pending environment access** |

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

## P5-D — Viewer-linked Scene Inspection — Complete

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

### P5-D completion

PR #43 merged as
`main@b086443d188eb9daae4bbf4f0faab3ff1d114f93` after the P5-D exact-head validation,
manual closeout, and independent review gates were completed. That evidence remains
historical P5-D evidence and is not inferred as P5-E validation.

## P5-E — Historical Result Workflow — Complete

P5-E extends the canonical P5-B result-open path with bounded historical discovery and
passive provenance while preserving P5-C logical storage and P5-D explicit Inspect.

Focused contract:
[`docs/P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

Delivered scope:

- separate max-10 MRU **Recent IQA Results** observer metadata;
- production logical Result locator `storage_root_id + relative_path`, resolved through
  current P5-C mappings at reopen time;
- manual v2 logical-history promotion only when P5-C resolves the proposed locator back
  to the same canonical opened directory; otherwise Local fallback;
- observed `result_id + schema_version` identity gate before replacing current Results;
- result-only browsing when native sources are missing/offline/unmapped;
- passive schema-v2 Provenance plus explicit historical/read-only schema-v1 treatment;
- feature-local resolver generation so delayed logical Recent work cannot override a
  newer File/Jobs/Recent Result-open intent;
- live Provenance refresh after Remote IQA root mapping changes;
- Session v1 and P4-C Recent Images/Folders/Sessions remain unchanged.

P5-E merged as PR #44 at
`main@6a0a334d61a7495b9c3433edfcbd537c8df59468`. Its validation evidence is historical
P5-E evidence and is not inferred as P5-F validation.

## P5-F — Integration & Performance Hardening — Complete

P5-F owns the repository-side hardening that is testable without the real external
GPU/SMB environment:

- isolates P5-B Result/Reference, P5-D verification/spatial, and P5-E historical
  resolver work from the local Statistics/Difference analysis pool;
- preserves the separate existing P5-C max-two job-operation pool;
- enables bounded HTTP connection reuse through lazy per-worker client checkout so
  queued/cleared workers own no physical HTTP client;
- preserves one-shot CREATE, polling, result-reference, cancel-race, publication, and
  durable-job-on-close semantics;
- extends the existing Copy Diagnostics surface with bounded Remote IQA counters;
- provides deterministic compatibility/result-characterization tools for later real
  environment use;
- adds structural stress coverage through 300 Scenes and queued-worker shutdown cases.

No raw-grid cache, speculative preload, adaptive polling, generalized retry, new
performance Settings, WebSocket, or optional detail viewer is introduced without real
evidence. No fixed wall-clock number is a correctness gate.

P5-F merged as PR #45 at
`main@6634447fc3c48545a2482718dd3f444928806218` after exact-head local validation and
independent review. The unavailable external environment was not treated as PASS, so
the overall **P5 program remains Active**.

## R — Repository Refactoring & Validation Hardening — Active

R is a behavior-preserving repository program between repository-side P5-F completion
and production-shaped P5-G integration. It owns small independently reviewed slices for
composition, resource ownership, targeted structural/test cleanup, offscreen validation
debt, and harness/documentation hardening. It does not change user-visible behavior,
schema, Session format, numerical semantics, source/residency policy, retry/polling,
worker concurrency, or server APIs.

The authoritative R plan is
[`docs/exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

| Order | Slice | Status |
|---|---|---|
| R0 | State reconciliation and executable program | **Complete — PR #46 · `a25b3ee1b08dc26b57776fd2a24c3b751f13ebfc`** |
| R1 | Application composition | **Complete — PR #47 · `808f1e6bccd67e649be71b03798a1a1f407628f8`** |
| R2 | Worker and resource ownership injection | **Complete — PR #48 · `7c0d326fd2a8ff767ac916d29af1c7d5ee44abd6`** |
| R3-A | Obsolete Remote scaffold disposition | **Complete — PR #49 · `a97bfb68e1113afea4ea905d7ccbbb1f67a9bde1`** |
| R3-B | Session and legacy boundary clarification | **Complete — PR #50 · `6e98baea425f3dfbfacc1140370a77e889673a76`** |
| R4-A | Common UI test fixtures | **Complete — PR #51 · `336a27e5e10e3d5e8d83bc18046bec837daa5b96`** |
| R4-B | Smoke suite decomposition | **Complete — PR #52 · `39b8c77fbf8a497d2787f33b8e119d2ddbed9604`** |
| R5 | Windows/offscreen validation hardening | **Complete — PR #53 · `45e718abe28ab600edab41cf04a998029f6fc5f7`** |
| R6 | Harness and architecture guardrails | **Complete — PR #54 · `7c3dbe386aaff900f0accc7ce460759df80f14e0`** |
| R7 | Final integration validation and closeout | **Active** |

## P5-G — External GPU/SMB Validation & Closeout — Deferred / pending environment access

P5-G is the final P5 program gate. When the real environment becomes available it will
validate:

- external GPU API/result-writer compatibility;
- Current Pair and Folder Pair end-to-end behavior;
- COMPLETE/PARTIAL and cancel/completion races;
- historical Result reopen/root remap;
- shared-root/staging/SMB behavior;
- manifest/summary/Reference/grid/native verification/spatial-load timing and byte
  observations;
- concurrent local analysis/navigation while remote work is active;
- close/reopen and rapid Result/Scene intents.

Only observed real-server/SMB evidence may be recorded as PASS. Any follow-up
optimization remains measurement-backed and bounded. P5-G performs the final P5 docs
closeout and activates P6 only after the external gate is actually observed.

The authoritative deferred gate is
[`docs/exec-plans/deferred/p5g-external-gpu-smb-validation.md`](exec-plans/deferred/p5g-external-gpu-smb-validation.md).

# P6 — Identity, Access & Remote Operations — Planned / next after P5 closure

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
