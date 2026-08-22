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
Scene / spatial inspection
```

Remote IQA remains feature-local. It does not extend
`Registered → Selected → Current Comparison Page → Presented → Resident` with a new
source owner.

## Numerical/result authority — schema v2

P5-A/schema v1 proved the original parser/fixture mechanics but remains historical
read-only compatibility. P5-A2 moved the durable numerical model to source-oriented
schema v2:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 separates `variant_id`, `source_id`, `scene_id`, and
`measurement_context_id` and stores server-authored W/S1/S2/count/valid source
measurements. PixelScope locally derives selected target/reference comparisons.

Key defaults remain:

- absolute Dataset Overview = `pooled_weighted_mean`;
- relative Dataset Overview = arithmetic mean of valid Scene comparison values;
- power mode 1 = ratio of pair-valid aggregate weighted means;
- power mode 2 = arithmetic mean of finite pair-valid grid log-ratios;
- signed attributes = pair-valid weighted target minus reference;
- v1 = explicit read-only compatibility with no synthetic v1→v2 upgrade.

Every published successful Scene binds every declared variant exactly once and obeys
the same geometry/numerical invariants whether the enclosing result is COMPLETE or
PARTIAL.

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
| 3 | P5-B IQA Workspace & Local Result Exploration | **Complete — PR #38 merged** |
| 4 | P5-C Submission & Shared Storage | **Active — Draft PR #42** |
| 5 | P5-D Viewer-linked Scene Inspection | Planned |
| 6 | P5-E Historical Result Workflow | Planned |
| 7 | P5-F Integration & Performance Hardening | Planned |

## P5-0 — P4 Closure & P5 Program Setup — Complete

PR #36 closed P4 and established the Remote IQA program, source-ownership boundary,
initial result contract, and P5 execution sequence.

## P5-A — Contract Fixtures & IQA Domain / schema v1 — Complete

PR #37 merged at `fceb16f6e43c48ec65fbf7ebbcc103b56716b686`.

It remains the historical executable schema-v1 baseline with deterministic fixtures,
safe bounded readers, W/S1/S2/count/valid recomposition, geometry utilities, and
explicit invalid/corrupt/unsupported handling.

## P5-A2 — Schema-v2 migration — Complete

### Stage 1 / PR #39 — Complete

Merged at `4f2d58f36152cbebd1110a2aed09afacc6f09596` and froze:

- `variant_id` / `source_id` / `measurement_context_id` identity;
- Scene-context-scoped absolute measurements;
- W/S1/S2/count/valid server authority;
- canonical absolute/relative reductions;
- default absolute and relative Dataset Overview semantics;
- v1 read-only compatibility;
- N-way result identity while keeping the initial submission UI two-variant.

### Stage 2 / PR #40 — Complete

Merged at `5fcea48bd80e7a9aa5f5caa42fdaabebb27256d6` and implemented:

- concrete v2 manifest/summary/grid models;
- JSON/NPZ dtype/rank/shape/safety constraints;
- deterministic measurement-context fingerprinting;
- exact complete-Scene variant/geometry/grid correspondence;
- finite-only Mode-2 behavior and centralized quality orientation;
- summary-first open with deferred Scene-grid access;
- deterministic N-way/golden/corruption/limit tests;
- explicit v1 dispatch.

P5-C later extends this same v2 reader with executable PARTIAL; there is no schema bump
and no second numerical parser.

## P5-B — IQA Workspace & Local Result Exploration — Complete

PR #38 merged into main at `a44978db783ebcecb0d55f8abb52b583e0fdc47c`.

Delivered:

- canonical **File > Open IQA Result...** version dispatch;
- summary-first schema-v2 Absolute default;
- N-way `variant_id` Reference switching;
- canonical relative math/reductions rather than UI-local duplicates;
- bounded background Reference preparation, one Scene grid at a time;
- stable Absolute/Relative table and Scene Trend presentation;
- rollback to last-valid presentation on deferred Reference failure;
- metadata-only Scene source cards;
- Plots-equivalent IQA dock float/dock/maximize/reset behavior;
- passive browsing with no Files/Selected/Primary/Difference/residency/native-analysis/
  Session mutation;
- v1 read-only historical compatibility.

P5-B is now the canonical local Results UI/controller reused by P5-C.

## P5-C — Submission & Shared Storage — Active / Draft PR #42

### Goal

Connect the merged P5-B/schema-v2 result path to an external job service while keeping
all portable identity explicit and preserving the local workspace.

### Delivered in current Draft

#### Typed Remote IQA settings — implemented

Application settings schema v6 adds:

```text
RemoteIqaSettings
    server_base_url
    storage_roots[] {
        storage_root_id
        client_path
    }
    staging_root_id
```

`storage_root_id + relative_path` is portable identity. `client_path` is machine-local
only; server physical paths and credentials are not serialized into requests/results.

#### Shared-storage resolution/staging — implemented, hardening pending

- most-specific configured logical root wins;
- existing sources are hashed and referenced in place;
- outside sources may be copied to content-addressed
  `staging/<sha256>/<basename>`;
- `.part` publication and atomic final replace/reuse verification are used.

Remaining hardening before merge: cross-process staging concurrency and symlink/
junction containment.

#### Deterministic two-variant submission — implemented

Initial user-facing submission stays exactly `A/B`:

- Current Pair = A/B pair of underlying Current Comparison Page documents;
- identity is independent from Primary/Active/view reorder/presentation transforms;
- Folder Pair uses immediate eligible non-symlink files, NFC lexical ordering, equal
  eligible counts, pair-by-index mapping, and equal pair dimensions;
- PNG/JPG/JPEG/BMP only; no silent RAW conversion;
- max 512 Scenes;
- request Scene IDs are deterministic `scene_000000...`;
- request payload contains portable root/path/SHA/dimensions only.

Arbitrary three-or-more-variant submission UI remains deferred. P5-B's N-way result
exploration remains independent of this submission-product scope.

#### Async HTTP Jobs lifecycle — implemented

```text
POST /v1/iqa/jobs
GET  /v1/iqa/jobs/{job_id}
GET  /v1/iqa/jobs/{job_id}/result
POST /v1/iqa/jobs/{job_id}/cancel
```

Polling is the initial progress path. CREATE is not auto-retried. Terminal
`succeeded`/`partial` result-reference retrieval is bounded/idempotent; after the
initial attempt, transient `GET /result` failures use 1s/2s/4s/8s retry backoff.

Completion never auto-opens Results. Users explicitly choose `Open Result`, which
resolves the logical result path through current settings and delegates to P5-B.

Client failures are classified as configuration, connection, timeout, HTTP, protocol,
or storage-resolution failures.

#### Executable PARTIAL schema-v2 result — implemented

PARTIAL uses the existing schema version 2:

- ordered `scene_outcomes[]` covers every requested Scene;
- statuses are `succeeded`, `failed`, or `cancelled`;
- failed/cancelled outcomes require bounded diagnostics;
- at least one Scene succeeds and at least one fails/cancels;
- `scenes[]` contains only fully published successful Scenes in request order;
- successful Scenes retain all normal v2 numerical/geometry/cardinality invariants;
- zero-success is FAILED/CANCELLED, not PARTIAL;
- all-success is SUCCEEDED/COMPLETE.

P5-B Results displays a compact partial-success summary and failed/cancelled Scene
diagnostics while preserving exploration of successful Scenes.

#### Debug/contract harnesses — implemented

Debug-only tools gated by `PIXELSCOPE_REMOTE_IQA_DEBUG` include:

- Request Inspector — production request builder without POST;
- Replay JSON — bounded logical terminal-job/result replay, no physical result path;
- deterministic COMPLETE/PARTIAL schema-v2 result generator reusing the canonical v2
  fixture writer/loader;
- real-socket localhost `ThreadingHTTPServer` fault harness for production-client
  normal/error/retry validation.

The localhost server is a debug test double, not the future GPU server implementation.

### Observed validation so far

- historical P5-C full-suite checkpoint: 809 pytest PASS plus Ruff/mypy/diff PASS at
  `04f8c08...` before later stages;
- Setup UX + Request Inspector focused/static validation PASS;
- Replay JSON + deterministic COMPLETE manual Open Result validation PASS;
- Stage-4 focused localhost/retry/submission/UI suite: **26 passed**;
- Stage-4 mypy: **102 source files, no issues**;
- real-socket localhost normal submission/poll/result-reference flow: manual PASS;
- `result-500-once`: first terminal `/result` 500 followed by automatic successful
  retry without resubmitting the same job; manually reproduced again with a second
  newly-created job.

Latest-head full repository validation is still pending and must not be inferred from
older checkpoints.

### Remaining P5-C merge blockers

1. shared staging cross-process concurrency + containment hardening;
2. cooperative cancellation/shutdown for in-flight staging/pre-create work;
3. duplicate in-flight submission prevention + explicit ambiguous-create UX/policy;
4. result-path remap race when Remote IQA settings change during an existing resolver;
5. final docs/static/full owner validation;
6. independent whole-PR latest-head re-review.

PR #42 remains Draft. P5-D must not start until these blockers are resolved and P5-C
is merged.

## P5-D — Viewer-linked Scene Inspection — Planned

After P5-C closes:

- explicit Inspect with P4-A Pick-state guard;
- canonical loading of only inspected Scene sources;
- logical-root + source-hash verification;
- transient return snapshot with stale-intent invalidation;
- IQA Reference independent from Primary;
- linked Scene navigation;
- exact analysis-grid → source → viewer mapping;
- vector/block overlay and block inspector from schema-v2 grids;
- safe interaction with Difference/Gain/ROI/Line.

## P5-E — Historical Result Workflow — Planned

Extend the existing canonical result-open path with:

- bounded Recent IQA Results;
- production logical-root reopen;
- immutable result/source-hash identity;
- result-only mode when sources are unavailable;
- source/hash mismatch diagnostics;
- provenance display;
- explicit v1 historical handling.

Session v1 is unchanged. Any future Session-carried IQA reference requires an explicit
new Session schema/version decision.

## P5-F — Integration & Performance Hardening — Planned

Validate the composed workflow against the real external service and realistic data:

- actual server adapter/protocol compatibility;
- SMB/network bandwidth and grid-loading behavior;
- bounded grid cache/preload tuning;
- reference-switch latency;
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
