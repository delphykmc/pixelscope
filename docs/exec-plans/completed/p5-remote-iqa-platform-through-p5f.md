# Execution plan: P5 — Remote IQA Platform

Status: Complete through **P5-F / PR #45**; P5-G transferred to the deferred external-environment plan
Owner: repository owner + P5 orchestrator + slice implementation/review agents
Last updated: 2026-08-24
Completion baseline: `main@6634447fc3c48545a2482718dd3f444928806218`

This is the retained historical P5 program plan through P5-F. The authoritative
unobserved P5-G gate now lives in
[`docs/exec-plans/deferred/p5g-external-gpu-smb-validation.md`](../deferred/p5g-external-gpu-smb-validation.md).
The current repository program is in
[`docs/exec-plans/active/next-phase.md`](../active/next-phase.md).

Authoritative P5 documents:

- product/transport/ownership contract:
  [`docs/REMOTE_IQA_CONTRACT.md`](../../REMOTE_IQA_CONTRACT.md)
- current numerical/result contract:
  [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)
- completed P5-D viewer-linked inspection contract:
  [`docs/REMOTE_IQA_VIEWER_INSPECTION.md`](../../REMOTE_IQA_VIEWER_INSPECTION.md)
- completed P5-E historical-result contract:
  [`docs/REMOTE_IQA_HISTORICAL_RESULTS.md`](../../REMOTE_IQA_HISTORICAL_RESULTS.md)
- P5-F integration characterization:
  [`docs/REMOTE_IQA_INTEGRATION_CHARACTERIZATION.md`](../../REMOTE_IQA_INTEGRATION_CHARACTERIZATION.md)
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
or an older P5-F head is not validation of the latest P5-F head. Localhost/mock evidence
never substitutes for an unobserved external GPU/SMB environment.

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

P5-F and P5-G must not create another authority for Files/Selected/Current Comparison
Page, source residency/protection/preload, Difference/cache, Display Gain, native
analysis, or Session v1.

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
[`docs/REMOTE_IQA_HISTORICAL_RESULTS.md`](../../REMOTE_IQA_HISTORICAL_RESULTS.md). Its validation is
historical evidence only and is not carried forward as P5-F PASS.

## P5-F completed scope — repository-side integration hardening

P5-F is the repository-side integration/characterization/hardening slice that can be
completed without access to the external GPU/SMB environment. It is not a new Remote
IQA architecture phase. The governing loop is:

```text
existing behavior
    ↓
characterize deterministic ownership/lifetime
    ↓
identify demonstrated duplicate work or contention
    ↓
minimal bounded correction
    ↓
regression evidence
```

No fixed wall-clock value is a correctness contract.

### P5-F1 — deterministic transport compatibility tooling

- preserve the frozen P5-C create/status/result/cancel state machine;
- keep CREATE single-shot/no-blind-retry semantics;
- model non-terminal cancel responses and completion/cancel races correctly;
- provide a bounded compatibility probe that can later be pointed at the real service;
- reuse localhost/debug harnesses for deterministic client-side evidence only.

### P5-F2 — worker and HTTP lifetime hardening

- isolate P5-B Result/Reference, P5-D verification/spatial, and P5-E historical resolver
  file/grid work from the local Statistics/Difference analysis pool;
- retain the existing separate max-two P5-C job-operation pool;
- reuse HTTP connection pools through the existing `client_factory` seam;
- use lazy physical HTTP checkout so queued/cleared workers own no client resource;
- keep idle clients bounded and close active clients deterministically after their worker
  returns during shutdown;
- extend the existing Copy Diagnostics surface with bounded worker/transport counters.

### P5-F3 — deterministic stress / lifecycle regressions

Exercise representative generated workloads for 1, ~10, ~50, ~150, and around ~300
Scenes without committed huge binaries. Structural assertions cover bounded ownership
rather than brittle timing thresholds.

Cover:

- COMPLETE/PARTIAL/failure/cancel state handling through inherited P5 suites;
- cancel response races in the compatibility probe;
- more queued HTTP operations than physical P5-C worker slots;
- shutdown while workers are running and additional work is queued;
- Remote IQA/local Statistics-Difference coexistence;
- production P5-B/P5-D/P5-E pool rebinding;
- stale callbacks, root remap, source verification, and no batch-owned residency through
  inherited regressions.

### P5-F4 — optimization decisions

P5-F does **not** add a raw-grid cache, speculative grid preload, adaptive polling,
generalized retries, new performance Settings, WebSocket, or optional detail viewer
without environment evidence that justifies the permanent product/resource contract.

Optional `detail_artifacts[]` remain opaque/deferred unless a stable typed server
contract and clear product need are observed. Filename conventions do not create a
contract.

## P5-F validation direction

Focused P5-F automated coverage prioritizes deterministic structure and lifecycle:

1. endpoint/state/result-reference regression and no blind create retry;
2. cancel-at-most-once with non-terminal cancel response races;
3. lazy/bounded HTTP client lifetime under queued work and shutdown;
4. production Result/Inspect/history worker ownership;
5. Remote IQA/local-analysis coexistence;
6. representative synthetic Scene counts;
7. diagnostics bounds/redaction;
8. inherited P5-B/C/D/E and schema-v1 regressions.

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

Only exact-head observed results may be recorded as PASS. A failing exact-head node may
be dispositioned as pre-existing/environmental debt only when that exact node reproduces
with the same failure on the recorded implementation base under the same environment.
That disposition is not a full-suite PASS and must remain explicit in validation reports.

## P5-F merge gate — satisfied by PR #45

P5-F merge recommendation required:

- repository-side implementation completion;
- focused deterministic P5-F regression PASS on the exact head;
- exact-head full repository/static validation execution, with either PASS or an
  independently reviewed base-main disposition for every identical failing node;
- independent latest-head whole-PR PASS;
- no unresolved correctness/lifetime/resource blocker;
- truthful characterization docs;
- owner approval.

**Real external GPU/SMB access is not a P5-F PR merge gate when that environment is
unavailable.** This is an explicit scheduling split, not a substitute PASS. Merging
P5-F may mark P5-F Complete, but it must **not** mark the overall P5 program Complete.

## P5-G — External GPU/SMB Validation & Closeout — transferred / pending environment access

P5-G remains the final P5 program gate and begins only when an external environment is
realistically available. It owns observation, not speculative redesign. The following
matrix is retained as historical program context; the deferred plan linked above is now
the execution source of truth.

Required real-environment validation:

- actual external GPU API/result-writer compatibility against the frozen P5-C transport
  and schema-v2 publication contracts;
- Current Pair and Folder Pair end-to-end execution;
- COMPLETE and PARTIAL publication behavior;
- early/late cancel and completion races;
- historical logical Result reopen/root remap;
- real shared-root/staging/SMB access;
- manifest/summary/Reference/Scene-grid/source verification/spatial-load timing and byte
  observations;
- concurrent local Statistics/Difference/Display Gain/ROI/Line/page navigation;
- close/reopen and rapid Result/Scene intents;
- server build/algorithm identity and storage topology capture where available.

Any performance correction in P5-G must still be measurement-backed and bounded. Real
timing observations do not become correctness thresholds unless a concrete regression
is intentionally frozen.

P5-G is also the only slice allowed to perform final P5 closeout:

1. record P5-F and P5-G merge/evidence identities;
2. mark the overall P5 Remote IQA Platform Complete;
3. retain this P5-through-P5-F plan under `docs/exec-plans/completed/`;
4. update ROADMAP/CURRENT_STATE/UI implementation status;
5. make P6 **Identity, Access & Remote Operations** the active/next program.

The implementation agent must never fabricate a live GPU/SMB PASS. Localhost/mock PASS
and compatibility tooling are preparation/evidence only.

## P6 boundary

P6 **Identity, Access & Remote Operations** is the next major program only after P5-G
and final P5 closeout. P5-F/P5-G do not implement authentication/SSO, credential
lifecycle, permission policy, audit, or result administration merely because a
production server may require those later.

## Completion summary

- Delivered behavior: repository-side Remote IQA client platform through P5-F, with
  schema-v2 numerical/result authority, canonical Results, submission/jobs/storage,
  explicit native Inspect, historical reopen, and bounded worker/transport lifetimes.
- Merge identity: P5-F / PR #45 at
  `main@6634447fc3c48545a2482718dd3f444928806218`.
- Remaining limitation: no real external GPU server or SMB environment has been
  observed; P5-G therefore remains deferred and overall P5 remains Active.
- Historical validation: PR #45 recorded 925 passed, 1 skipped, and the same three
  Windows offscreen Qt/pyqtgraph failures reproduced on its base. This is not a current
  full-suite PASS and not external-environment evidence.
