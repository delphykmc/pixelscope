# Execution plan: P5 — Remote IQA Platform

Status: Active — **P5-F Integration & Performance Hardening**
Owner: repository owner + P5 orchestrator + slice implementation/review agents
Last updated: 2026-08-23
Current merged main: `6a0a334d61a7495b9c3433edfcbd537c8df59468`

Authoritative P5 documents:

- product/transport/ownership contract:
  [`docs/REMOTE_IQA_CONTRACT.md`](../../REMOTE_IQA_CONTRACT.md)
- current numerical/result contract:
  [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)
- completed P5-D viewer-linked inspection contract:
  [`docs/P5D_VIEWER_INSPECTION.md`](../../P5D_VIEWER_INSPECTION.md)
- completed P5-E historical-result contract:
  [`docs/P5E_HISTORICAL_RESULTS.md`](../../P5E_HISTORICAL_RESULTS.md)
- P5-F integration characterization:
  [`docs/P5F_INTEGRATION_CHARACTERIZATION.md`](../../P5F_INTEGRATION_CHARACTERIZATION.md)
- historical schema-v1 compatibility:
  [`docs/REMOTE_IQA_V1_SPEC.md`](../../REMOTE_IQA_V1_SPEC.md)
- current repository snapshot:
  [`docs/CURRENT_STATE.md`](../../CURRENT_STATE.md)
- program roadmap:
  [`docs/ROADMAP.md`](../../ROADMAP.md)

## Program governance

P5 remains an orchestrated multi-PR program.

- **P5 orchestrator** owns cross-slice contracts, execution order, durable docs,
  owner-decision gates, and evaluation of implementation/review evidence.
- **Implementation agents** modify only the delegated slice and do not redefine
  numerical/source/session authorities ad hoc.
- **Independent reviewers** inspect the latest full PR head without modifying the branch.
- **Repository owner** runs requested local Windows validation and approves merge.

Observed evidence and planned validation remain separate. A PASS from P5-C/P5-D/P5-E
or an older P5-F head is not validation of the latest P5-F head.

## Product flow

```text
local inspection
    ↓ optional remote work
Current Pair / Folder Pair submit
    ↓
non-modal durable job
    ↓
continue local work
    ↓
explicit Open Result
    ↓
Absolute / Relative result exploration
    ↓
Recent IQA Result historical reopen
    ↓ optional
explicit Inspect in Viewer
    ↓
verified native Scene sources + spatial grid inspection
    ↓
explicit Return to prior local comparison
```

The external GPU model/server remains outside this repository. PixelScope owns client
preparation, transport contract, portable storage identity, stable result parsing,
local reference-dependent exploration, historical-result discovery, and viewer-linked
inspection.

## Inherited authority

The sole local runtime/source hierarchy remains:

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

P5-F must not create another authority for Files/Selected/Current Comparison Page,
source residency/protection/preload, Difference/cache, Display Gain, native analysis,
or Session v1.

The canonical Result path remains P5-B with P5-A2/v1 reader dispatch. P5-D remains the
only explicit native source verification/Inspect bridge. P5-E remains the historical
locator/identity/provenance authority.

## Completed P5 baseline

| Slice | Status | Authority |
|---|---|---|
| P5-0 | Complete — PR #36 | program setup/contracts |
| P5-A | Complete — PR #37 | historical executable schema v1 |
| P5-A2 Stage 1 | Complete — PR #39 | durable schema-v2 model |
| P5-A2 Stage 2 | Complete — PR #40 | executable schema-v2 reader/math/artifacts |
| P5-B | Complete — PR #38 | canonical local IQA Results workspace |
| P5-C | Complete — PR #42 | submission/shared storage/jobs/PARTIAL |
| P5-D | Complete — PR #43 | verified viewer-linked Scene Inspect/Return |
| P5-E | **Complete — PR #44** | historical locator/identity/Provenance/result-only mode |

P5-B merged at `a44978db783ebcecb0d55f8abb52b583e0fdc47c`.
P5-D merged at `b086443d188eb9daae4bbf4f0faab3ff1d114f93`.
P5-E merged as current `main@6a0a334d61a7495b9c3433edfcbd537c8df59468`.

## Current executable schema-v2 contract

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 separates stable `variant_id`, concrete `source_id`, evaluation `scene_id`,
and `measurement_context_id`. Server-authored W/S1/S2/count/valid remain measurement
authority. PixelScope derives pair-valid comparisons with canonical helpers.

Optional `storage_root_id` is source-location metadata only and is excluded from
immutable source equality and measurement-context identity. Schema v1 remains explicit
read-only compatibility.

## P5-E completed scope

P5-E delivered the historical-result layer without changing canonical Result or source
authority:

- typed logical/local historical locators;
- independent max-10 Recent IQA Results observer metadata;
- `result_id + schema_version` historical identity gate before presentation;
- current-mapping logical root resolution and remap handling;
- result-only mode when native Scene sources are unavailable;
- passive Provenance in the existing Results workspace;
- explicit schema-v1 historical/read-only treatment;
- stale resolver rejection across File/Jobs/Recent open intents;
- Session v1 unchanged.

The detailed merged P5-E authority remains in
[`docs/P5E_HISTORICAL_RESULTS.md`](../../P5E_HISTORICAL_RESULTS.md). Its validation is
historical evidence only and is not carried forward as P5-F PASS.

## P5-F active scope

P5-F is a final integration/characterization/hardening slice, not a new Remote IQA
architecture phase. The governing loop is:

```text
existing behavior
    ↓
instrument / characterize
    ↓
identify actual bottleneck or duplicate work
    ↓
minimal bounded correction
    ↓
measure again
```

No fixed wall-clock value is a correctness contract.

### P5-F1 — Real GPU Server Compatibility

- validate actual external GPU API/result writer compatibility against the frozen P5-C
  transport and schema-v2 publication contracts;
- reuse/extend localhost/debug harnesses for deterministic client-side compatibility
  evidence;
- record transport-compatible differences additively;
- record contract contradictions as external integration blockers rather than silently
  normalizing source order, logical storage, publication, geometry, or numerical meaning.

### P5-F2 — SMB / Network / Grid Performance Characterization

Characterize separately:

- preflight/header/hash/shared-root/staging/create;
- status polling/result-reference recovery;
- historical logical resolution/manifest/summary/initial presentation;
- first/repeated Reference preparation and Scene-grid loading;
- source resolution/hash/read/decode/verified commit;
- spatial Scene-grid load/overlay preparation.

Prefer bounded monotonic timing, counts, byte counts, cache hits/misses, and worker
activity. Do not retain source arrays, whole HTTP bodies, or unbounded per-Scene history.

### P5-F3 — Measured bounded optimization

Only measured findings may justify changes such as:

- isolating Remote IQA blocking work from the local Statistics/Difference analysis pool;
- reusing the existing HTTP client/session lifetime when the current composition defeats
  connection pooling;
- bounded read retry/backoff where transient behavior demonstrates benefit;
- a byte-budgeted current-result raw-grid cache or at-most-one adjacent preload only if
  repeated grid I/O is materially harmful.

A raw-grid cache and speculative grid preload are not default deliverables.

### P5-F4 — Stress / Failure / Lifecycle Hardening

Exercise deterministic representative workloads for 1, ~10, ~50, ~150, and around
~300 compared sources where practical without committed huge binaries. Structural
assertions cover bounded worker/memory/I/O ownership rather than brittle timing gates.

Cover COMPLETE/PARTIAL/failure/cancel, transient network/storage failures, rapid Result
and Scene intents, close/recreate, local workflow coexistence, root remap, hash mismatch,
and stale callback rejection.

### P5-F5 — Optional Detail Characterization + P5 closure preparation

Optional `detail_artifacts[]` stay opaque/deferred unless a stable typed server contract
and clear product need are observed. Filename conventions do not create a contract.

P5-F prepares the P5 completion summary but remains Active while its PR is unmerged.
After P5-F merge, a tiny docs-only closeout records the actual merge SHA, marks P5
Complete, archives the active plan, and makes P6 the active program.

## Automated validation direction

Focused P5-F automated coverage must prioritize deterministic structure and lifecycle:

1. real-contract HTTP JSON fixture compatibility;
2. endpoint/state/result-reference regression and no blind create retry;
3. one poll in flight and HTTP client/session lifetime;
4. slow-filesystem/SMB-like contention and Remote IQA/local-analysis coexistence;
5. summary-first Result open and Reference/grid I/O counts;
6. repeated Reference/grid access behavior;
7. source verification and staging streaming/bounds;
8. representative synthetic Scene counts;
9. COMPLETE/PARTIAL/failure/cancel/recovery;
10. Recent remap/offline/identity and Inspect/hash/root-remap;
11. stale callbacks, close/recreate, and no batch-owned residency;
12. v1 compatibility and full P5-B/C/D/E regressions.

Performance evidence is observational unless a specific regression is later frozen.

## Owner manual / real-server gate

The implementation agent must not fabricate a live GPU/SMB PASS. Real-server owner
validation records client head SHA, server build/algorithm identifiers when available,
Scene/source counts, storage topology, and observed timings for Current Pair, Folder
Pair, PARTIAL, Cancel, Historical, SMB/staging, and concurrent local use.

The repository-standard Windows validation remains:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Only observed results may be recorded as PASS.

## P5-F merge gate

P5-F merge recommendation requires implementation completion, no blocking external
protocol contradiction, deterministic localhost/mock regression PASS, exact-head full
repository validation PASS, owner Windows real-server/manual validation, independent
latest-head whole-PR PASS, no unresolved correctness/lifetime/resource blocker,
truthful characterization docs, and owner approval.

Do not mark P5-F or P5 Complete while the P5-F PR is unmerged.

## P6 boundary

P6 **Identity, Access & Remote Operations** is the next major program after P5 closure.
P5-F does not implement authentication/SSO, credential lifecycle, permission policy,
audit, or result administration merely because a production server may require those
later.
