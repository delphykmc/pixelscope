# Roadmap

## Delivered baseline

### P0/P1 — Product foundation — Complete

PixelScope provides local image registration/selection, one-to-six-image synchronized
comparison, Statistics, Histogram, Line Profile, Difference, Split Channels, RAW
loading, fixed comparison layouts, and stable local viewer/navigation behavior.

P1-D/P1-E/P1-F workspace-polish work completed as PR #10–#12.
Historical plan:
[`docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md).

### P2 — Runtime Foundation, Settings & Performance — Complete

Completed sequence:

`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`

Delivered contracts include typed settings schema v5, independent Difference/source
memory budgets, byte-budgeted decoded-source LRU residency, bounded Current Comparison
Page protection, max-one speculative folder preload, RUNNING preload foreground
promotion, deterministic diagnostics, and bounded application worker ownership.

P2-F merged as PR #20 at
`9c66629f6392971b8c52ac9dff27b16166cf9829`.
Historical plan:
[`docs/exec-plans/completed/p2-runtime-foundation-settings-performance.md`](exec-plans/completed/p2-runtime-foundation-settings-performance.md).

### P3 — Image Semantics & RAW Processing — Complete

P3 established the authoritative local image hierarchy:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset
Current Comparison Page        # max 6
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

P3 delivered Gray/mixed-bit Difference semantics, native RAW authority, presentation-
only Display Gain, large logical Selected sets, six-image Current Comparison Pages,
unified image/folder opening, lazy RAW profile resolution, and integration hardening
without Selected-wide eager decode.

P3 completed with PR #27 at
`835634a58609601605fd0fc18a3028b64225f535`.
Historical plan:
[`docs/exec-plans/completed/p3-image-semantics-raw-input.md`](exec-plans/completed/p3-image-semantics-raw-input.md).

### P4 — Workflow & Session Productivity — Complete

P4 delivered temporary Pick/Keep curation, Comparison Set/Session persistence, typed
Recent entries, Difference/source-curation lifecycle alignment, focused analysis
exports, and composed workflow hardening while preserving P2/P3 source ownership.

P4-F merged as PR #35; the P4-complete baseline is
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`.

Completed P4 plan:
[`docs/exec-plans/completed/p4-workflow-session-productivity.md`](exec-plans/completed/p4-workflow-session-productivity.md).

Deferred from P4, not completion blockers: saved/named/multiple ROI, Alpha Overlay /
Flicker / Wipe, and arbitrary-angle Line Profile with an explicit sampling contract.

## Forward sequence

`P5 Remote IQA Platform`
→ `P6 Identity, Access & Remote Operations`
→ `P7 Release Engineering & Distribution`

P5 is the active program.

Active execution/orchestration plans:

- [`docs/exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- [`docs/exec-plans/active/p5-schema-v2-revision.md`](exec-plans/active/p5-schema-v2-revision.md)

Remote IQA product contract:
[`docs/REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Current executable P5 numerical/result target:
[`docs/REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).

Historical merged schema-v1 specification:
[`docs/REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).

# P5 — Remote IQA Platform — Active

## Product objective

P5 connects the local PixelScope engineering workflow to an external GPU IQA service
without turning remote jobs/results into local source ownership.

```text
fast local PixelScope inspection
        ↓ when needed
submit current pair or large IQA evaluation
        ↓ non-modal remote job
continue local work
        ↓
open durable IQA result
        ↓
absolute/relative Dataset Overview
        ↓
attribute Scene Trend / outliers
        ↓
Scene
        ↓
spatial block inspection in existing viewer
```

Remote IQA is feature-local and does not replace
`Registered → Selected → Current Comparison Page → Presented → Resident`.

## P5 numerical ownership — executable schema v2

The governing model is:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

The server owns source decoding, IQA extraction, Scene-context weighting/gating,
validity, geometry, W/S1/S2/count/valid, absolute summary projections, and provenance.
PixelScope selects `variant_id` Reference and derives target/reference values locally.
It never recomputes IQA from source pixels, reverse-engineers weights, or aligns/
resizes incompatible published grids.

### Identity

- `variant_id` identifies one comparison/configuration across Scenes.
- `source_id` identifies one concrete source image.
- `scene_id` identifies one evaluation Scene.
- `measurement_context_id` identifies the Scene-context-specific weighted
  measurement.

The same `source_id` may recur in different Scenes when its immutable source metadata
is identical. That reuse does not make the weighted measurements reusable across
contexts. Duplicate `source_id` binding inside one complete Scene is invalid.

`measurement_context_id` is executable as `mc2:<64 lowercase SHA-256 hex>` over
canonical Scene/source/provenance/geometry JSON.

### Complete result geometry/cardinality

A normal complete Scene contains exactly one source per declared variant in exact
variant order. All variants have equal original dimensions. Stage-2 schema v2 freezes
exact equality of duplicated SceneGeometry and per-attribute GridGeometry across
variants. PixelScope does not manufacture physical correspondence.

### Numerical authority and summaries

Per source/attribute/grid the server publishes:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid_mask
```

Canonical Scene mean is `ΣS1/ΣW`; weighted population std comes from W/S1/S2.
Server-written mean/std values are projections only and must agree within the v2
projection tolerance.

Schema v2 publishes both pooled-weighted and equal-Scene absolute Dataset summaries.
**Default absolute Dataset Overview = pooled weighted mean.**

### Reference-neutral local comparison

Schema-v2 serialized operators are:

```text
power_ratio_target_over_reference_db
signed_target_minus_reference
```

The v1 A/B operator names remain historical v1 compatibility only.

Pair-valid support is target-valid AND reference-valid on a validated common grid.
Power mode 1 is ratio of pair-valid aggregate weighted means. Power mode 2 is the
unweighted arithmetic mean of finite pair-valid grid log-ratios. Signed attributes use
pair-valid weighted target mean minus reference mean.

One Qt-free executable helper owns user-facing quality orientation for both power
modes:

- higher-is-better: quality = raw;
- lower-is-better: quality = -raw;
- signed/neutral: quality N/A.

**Default relative Dataset Overview = arithmetic mean of valid per-Scene selected
comparison values.**

## Remote analysis domain and spatial convention

Remote 4K-class RGB inputs may be analyzed in an approximately 2K domain. No fixed
resize factor is assumed. Result geometry carries explicit source-to-analysis affine,
valid rectangle, grid origin/block size, and discarded borders. Continuous pixel-edge,
half-open, row-major affine geometry from the v1 contract remains the baseline.

Stage 2 deliberately requires exact cross-variant geometry metadata equality for a
complete v2 Scene; P5-D uses the published mapping rather than inventing alignment.

## Remote input and deterministic submission baseline

Current remote submission policy remains PNG/JPG/JPEG/BMP with no silent RAW
conversion until P5-C explicitly changes it.

The v2 request/result identity model is N-way-capable, while the first P5-C
user-facing submission workflow remains exactly two variants: Current Pair and
deterministic two-folder Pair. Arbitrary N-way submission UI is deferred. This does
not limit P5-B from opening externally produced N-way v2 results.

## Result and bandwidth strategy

Executable schema v2 uses:

```text
result/
    manifest.json
    summary.npz
    scenes/<scene_id>.npz
    detail/... optional opaque references
```

Purpose-based artifact categories are:

1. summary metadata for fast absolute Dataset/Scene exploration;
2. Scene grid measurements for local relative and spatial work;
3. optional detail artifacts whose typed decode schema is deferred to P5-D.

Ordinary v2 open performs filesystem I/O only for manifest + summary. Deferred grid/
detail references receive host-independent syntactic path validation at open; actual
existence/resolution/content checks occur when requested. This avoids an O(Scene)
filesystem metadata sweep on SMB during initial overview.

Loading/cache/preload behavior remains a bounded, stale-safe performance policy, not a
numerical schema rule. P5-F owns measured SMB/cache policy.

Schema v1 remains explicit read-only compatibility. There is no synthetic v1-to-v2
upgrade.

## Shared storage and HTTP direction

Client/server may mount shared storage differently. P5 uses logical storage-root ID +
relative path rather than machine-local paths in durable transport/result identity.
Machine-local root mapping ownership remains a P5-C gate.

The external server currently has blocking HTTP behavior. P5-C targets async
submit/status/result/cancel with polling first; WebSocket progress remains optional.

## PARTIAL/failure direction

Durable PARTIAL results remain owner-approved so successful Scene work can be
preserved. The concrete PARTIAL manifest/failure taxonomy remains P5-C work.

Stage-2 executable behavior is intentionally `UNSUPPORTED` for
`publication_state=partial`; P5-B must not invent a parser. Unevaluable/incompatible
cohorts are rejected/excluded by server evaluation rather than repaired locally.

## UX direction

P5 adds one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

- batch references are not eagerly Registered/Selected/decoded;
- jobs do not forcibly replace local workspace;
- passive results do not mutate Selected;
- summary metadata provides initial absolute Overview/Scene Trend;
- IQA Reference uses `variant_id` and is independent from Primary;
- relative views derive locally from v2 source measurements;
- grid I/O/calculation is asynchronous/stale-safe;
- explicit Inspect later loads only chosen Scene sources through canonical local
  authority;
- result navigation drills down Dataset → attribute → Scene → block.

# P5 execution sequence

`P5-0 → P5-A(v1) → P5-A2(schema-v2 migration) → P5-B → P5-C → P5-D → P5-E → P5-F → P5 Complete`

## P5-0 — P4 Closure & P5 Program Setup — Complete

Docs-only orchestration slice that closed P4 and established the original P5 program.
Merged as PR #36.

## P5-A — Contract Fixtures & IQA Domain / schema v1 — Complete

Merged as PR #37 at
`fceb16f6e43c48ec65fbf7ebbcc103b56716b686`. It remains the historical executable
schema-v1 baseline and read-only compatibility implementation.

## P5-A2 — Schema v2 source-measurement migration — Active

### Stage 1 — durable contract revision — Complete

PR #39 merged at `4f2d58f36152cbebd1110a2aed09afacc6f09596` and froze the server-measurement /
client-comparison ownership model, N-way identity, Scene-context semantics, absolute
and relative reduction hierarchy, v1 compatibility, and PARTIAL direction.

### Stage 2 — focused executable-v2 migration — Active / Draft PR #40

Branch: `feature/p5-a2-executable-schema-v2`.

Stage 2 implements/finalizes:

- versioned v2 Qt-free domain and canonical v1/v2 dispatch;
- deterministic N-way v2 fixture writer;
- concrete manifest/summary/Scene-grid field placement;
- dtype/rank/shape and parser safety ceilings;
- deterministic `measurement_context_id`;
- cross-Scene concrete-source reuse policy;
- exact complete-result cardinality and geometry/grid correspondence;
- W/S1/S2 Scene and Dataset projection verification;
- reference-neutral target/reference operators;
- centralized raw/quality direction semantics for both power modes;
- summary-first deferred-grid filesystem boundary;
- repository-native v2 numerical/corruption/safety goldens plus real v1 dispatch
  regression;
- durable executable schema documentation.

PR #40 remains Draft until independent re-review and repository-pinned validation are
observed. It must not be merged merely from reduced-harness evidence.

## P5-B — IQA Workspace & Local Result Exploration — Paused / schema-dependent

PR #38 remains untouched while Stage 2 is active. After PR #40 merges, P5-B rebases
onto executable v2 and adapts behavior to:

- N-way `variant_id` Reference selection;
- summary-first absolute Dataset/Scene views;
- pooled absolute default;
- locally derived target/reference relative values;
- centralized quality orientation;
- equal-Scene relative Dataset default;
- non-blocking stale-safe Scene-grid work;
- passive local-workspace independence.

## P5-C — Submission & Shared Storage — Planned

P5-C owns logical-root client configuration, safe staging, deterministic two-variant
Current Pair/two-folder Pair submission, HTTP job lifecycle, polling Jobs UI, and the
detailed PARTIAL/failure/cancel/publication contract.

## P5-D — Viewer-linked Scene Inspection — Planned

P5-D connects selected Scene/grid anomalies to the existing viewer using the exact
published geometry. Before consuming optional detail maps it must define a typed,
versioned detail sub-schema; Stage-2 bare detail references are intentionally opaque.

## P5-E — Historical Result Workflow — Planned

P5-E adds bounded Recent IQA Results, production logical-root reopen, immutable
result/source-hash identity, result-only mode when sources are unavailable, provenance,
and v1 read-only historical handling. Session v1 remains unchanged.

## P5-F — Integration & Performance Hardening — Planned

P5-F validates real schema-v2 server compatibility, realistic result sizes, SMB/network
latency, grid cache/preload policy, local reference-switch latency, cancellation,
missing/corrupt artifacts, stale callbacks, teardown, and proof that remote membership
does not become local source ownership.

No fixed wall-clock latency is a schema correctness gate.

# P6 — Identity, Access & Remote Operations

Planned after P5: Login/SSO, token/credential lifecycle, permission/access policy,
audit integration, and controlled operational administration.

# P7 — Release Engineering & Distribution

Planned after P6: exactly PyInstaller 5.7 `onedir`, portable ZIP, Inno Setup,
packaging/signing/update/release validation, and distribution hardening.