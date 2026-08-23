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
`d1d1fbe8fc7ee855e5e037bcecc1278435e298`.
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

P5-D completed implementation contract:
[`docs/P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md).

P5-E historical-result contract:
[`docs/P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

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
explicit Inspect in Viewer when native sources verify
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
| 4 | P5-C Submission & Shared Storage | Complete — PR #42 |
| 5 | P5-D Viewer-linked Scene Inspection | **Complete — PR #43 · `b086443d188eb9daae4bbf4f0faab3ff1d114f93`** |
| 6 | P5-E Historical Result Workflow | **Active** |
| 7 | P5-F Integration & Performance Hardening | Planned — next |

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
repository validation PASS. Those results are historical P5-C evidence only.

## P5-D — Viewer-linked Scene Inspection — Complete

PR #43 merged as
`main@b086443d188eb9daae4bbf4f0faab3ff1d114f93` after exact-head automated validation
and independent review PASS.

P5-D completed the viewer-linked inspection contract without creating another source,
viewer, or residency owner:

- passive Results remain independent from local Selected until explicit **Inspect in Viewer**;
- exact encoded bytes are SHA-256 verified before native registration/presentation;
- logical-root remap, missing/hash/dimension/decode/containment failures fail inspection
  without invalidating the server Result;
- repeated `source_id` variant aliases retain one native source identity;
- first successful Inspect freezes one transient Return snapshot and newer local intent
  invalidates it rather than being overwritten;
- schema-v2 geometry drives vector/block overlays and Block Inspector values;
- generation/result/Scene/local-intent/settings/spatial-request keys reject stale work;
- new Result open and shutdown cancel/drop feature-local verification/spatial work.

Frozen implementation and validation contract:
[`docs/P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md).

## P5-E — Historical Result Workflow — Active

P5-E adds durable historical-result discovery **in front of** the existing canonical
P5-B result loader/workspace and optional P5-D Inspect. It does not add a second parser,
workspace, source resolver, or numerical authority.

Focused contract:
[`docs/P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

### P5-E1 — Historical Result Locator

- Qt-free typed production locator: `storage_root_id + relative_path`;
- Qt-free machine-dependent local absolute locator for manual/out-of-root/v1 results;
- logical locators resolve at reopen time through the current Remote IQA settings;
- successful-open identity is the observed `result_id + schema_version` only;
- Recent reopen identity mismatch is rejected before current Results presentation changes.

### P5-E2 — Recent IQA Results

- dedicated typed observer repository under `recent/iqa_results`;
- explicit history payload version, bounded/untrusted parsing, max 10 entries;
- MRU ordering and locator-based dedup independent from Recent Images/Folders/Sessions;
- successful File, Jobs, and Recent opens record; failed opens never record;
- manual v2 opens under a configured root canonicalize to the most-specific logical root;
- Jobs opens preserve the published logical locator rather than the current mapped drive path;
- missing/offline/remapped entries remain until explicit Remove/Clear.

### P5-E3 — Result-only & Source Diagnostics

- valid Results remain browsable when original native sources are missing, offline,
  unmapped, changed, or not portably located;
- no dataset-wide source stat/hash pass occurs at Result open;
- source existence/dimension/SHA/containment remains explicit P5-D Inspect authority;
- cheap published-locator availability and current selected-Scene native-inspection state
  are presented without declaring the Result corrupt.

### P5-E4 — Provenance & Historical Compatibility

- one compact Provenance page inside the existing Results workspace;
- schema-v2 Result, selected Scene measurement-context provenance, and source binding
  identity are displayed exactly as published;
- COMPLETE/PARTIAL remains explicit and PARTIAL failed/cancelled diagnostics remain intact;
- schema v1 remains explicit historical read-only compatibility with no synthetic
  storage root, measurement context, or v2 absolute measurements.

### P5-E5 — Integration / Validation / Closeout

- rapid Recent A→B, root-remap, current-result preservation, close/recreate, and P5-D
  new-result teardown regressions;
- Session v1 and existing Recent Images/Folders/Sessions remain unchanged;
- owner manual validation covers Recent/MRU/Clear, remap, offline, result-only,
  identity replacement, provenance/v1/PARTIAL, and lifecycle behavior;
- independent latest-head whole-PR review plus full repository validation precede merge.

P5-E remains **Active** until its PR is merged.

## P5-F — Integration & Performance Hardening — Planned

P5-F is the next planned slice. P5-E documents this handoff but does not implement it.

### P5-F1 — Real GPU Server Compatibility

- validate actual external GPU API/result-writer compatibility;
- reconcile protocol edge cases against the frozen client/result contracts.

### P5-F2 — SMB / Network / Grid Performance Characterization

- characterize realistic SMB/shared-storage filesystem calls, bandwidth, and latency;
- measure Result open, Reference/grid preparation, historical reopen, and Inspect paths.

### P5-F3 — Cache / HTTP / Retry / Backoff Tuning

- tune HTTP session reuse, polling/backoff, and result-reference retry from measurements;
- add bounded grid cache/preload only where measurements justify it.

### P5-F4 — Stress / Failure / Lifecycle Hardening

- large batches and COMPLETE/PARTIAL/failure/cancel cases;
- disconnect/reconnect, stale callbacks, close/recreate, repeated historical reopen/Inspect;
- proof remote batch membership never becomes local source/residency authority.

### P5-F5 — Optional Detail Characterization + P5 Closure

- characterize optional detail artifacts and decide whether typed detail-map support is
  justified;
- complete P5 closure docs and archive the completed P5 execution plan.

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
