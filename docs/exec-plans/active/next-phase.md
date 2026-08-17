# Execution plan: P5 — Remote IQA Platform

Status: Active — P5-0 program setup
Owner: repository owner + P5 orchestration agents
Last updated: 2026-08-17
Inherited merged baseline: PR #35 / main
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`

Authoritative remote IQA product/data contract:
[`docs/REMOTE_IQA_CONTRACT.md`](../../REMOTE_IQA_CONTRACT.md).

Completed P4 plan:
[`docs/exec-plans/completed/p4-workflow-session-productivity.md`](../completed/p4-workflow-session-productivity.md).

## Goal

P5 connects PixelScope to an external GPU Image Quality Assessment service without
turning remote results into a second PixelScope source/runtime authority.

The user workflow is deliberately two-speed:

1. use existing PixelScope local comparison tools for fast image inspection;
2. submit a current pair or a large folder-pair evaluation when remote IQA is useful;
3. continue local work while the remote job runs;
4. reopen durable results and drill down from dataset trend to attribute, scene, and
   spatial block;
5. explicitly inspect a selected scene in the existing PixelScope viewer.

P5 is client/result-platform work in `delphykmc/pixelscope`. GPU model and server
implementation remain in the external server repository, although P5 may define and
request new versioned interfaces from that service.

## Inherited P2/P3/P4 contracts

The following PixelScope hierarchy remains authoritative:

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

P5 must preserve these invariants:

- batch IQA membership is not Files registration or Selected membership;
- remote result membership does not own decoded-source residency/protection;
- IQA browsing starts no P2 folder preload or Comparison Page preload;
- IQA state does not bump source generations or redefine native source identity;
- existing Statistics/Histogram/Line Profile remain native local analysis of the
  Current Comparison Page;
- existing Difference numerical/cache/provenance rules remain unchanged;
- Display Gain remains presentation-only and cannot alter IQA server result identity;
- P4-A temporary Picks remain source-curation state and must not be silently
  invalidated by passive IQA browsing;
- Session v1 remains durable local workspace intent, not a container for remote
  numeric arrays or running jobs;
- P4 export remains a consumer of established local results and is not repurposed as
  remote-result authority;
- existing bounded application workers and stale-result/lifetime rules must not be
  bypassed by remote UI callbacks.

## P5 remote authority model

P5 models remote IQA independently from the local image hierarchy:

```text
IQA Job
    ↓
Scene
    ├─ Source A
    ├─ Source B
    ├─ future Source C ...
    ├─ representative image
    ├─ common Edge Map
    ├─ common Texture Gate
    └─ per-source attribute results
          ↓
     derived comparisons
```

The P5 v1 UI supports two sources per Scene, but the durable result/request schema
should use `sources[]` so future N-source evaluations do not require a format
redesign. Source A is the default reference, not an intrinsic ground truth.

The common Edge Map and Texture Gate are generated from a representative image for
the Scene and are shared by all sources in that Scene. Server weighting may be soft
or hard-gated and is server-profile authority; PixelScope must not infer an effective
numerical weighting policy from the visualization maps.

## Attributes and statistics

P5 starts with ten attributes:

| Attribute | Quality direction | Current default block |
|---|---|---:|
| Luma noise | lower is better | 32×32 px |
| Luma detail | higher is better | 32×32 px |
| Chroma noise | lower is better | 32×32 px |
| Chroma detail | higher is better | 32×32 px |
| Edge strength | higher is better | 32×32 px |
| Luma contrast | higher is better | 128×128 px |
| Luma bias | neutral / signed | 128×128 px |
| Chroma contrast | higher is better | 128×128 px |
| Chroma bias | neutral / signed | 128×128 px |
| Colorfulness | higher is better | 128×128 px |

Block sizes are server metadata, not PixelScope constants.

The server exposes weighted mean and weighted population standard deviation, plus two
official comparison summaries for power attributes:

- ratio of weighted means;
- mean of per-grid log ratios.

P5 must preserve the distinction. Bias attributes are signed-value comparisons and
must not be presented as ordinary dB power-ratio quality metrics.

## Remote analysis geometry

GPU analysis operates on an approximately 2K-downscaled domain for 4K-class RGB
inputs. Structural maps, attribute maps, weights, and grid summaries are therefore
remote-analysis-domain data.

The result contract must carry original/analysis dimensions, valid rectangle,
source-to-analysis transform, grid origin/dimensions, block size, and border-discard
metadata. PixelScope must map remote grid coordinates back through this metadata to
the original viewer; a fixed 0.5 scale is not a contract.

Pair dimensions must match. Dimension mismatch fails evaluation rather than silently
creating a client-side alignment/resize semantic.

## Result strategy

P5 uses tiered durable results:

1. **Job summary** — small immutable manifest + summary statistics, loaded when a
   result opens.
2. **Compact scene spatial data** — source-local weighted block values/sufficient
   statistics, loaded lazily for an inspected scene.
3. **Optional 2K detail artifacts** — per-pixel attributes and structural maps,
   loaded only when explicitly needed in a future/detailed workflow.

Metadata is JSON-friendly. Numeric matrices should use NumPy-friendly binary
artifacts instead of large nested JSON float arrays.

Completed results are historical engineering artifacts and are expected to remain
available until explicitly/admin deleted. P5 therefore treats result reopen/history
as a product requirement, not an optimization.

## Shared storage and transport

Client and GPU server may mount the same SMB/network storage at different physical
paths. P5 uses logical storage roots plus relative paths rather than embedding
machine-local paths in the server API.

Example:

```text
storage_root_id = iqadata
relative_path = project42/A/0001.png

client: iqadata → G:\IQA
server: iqadata → /home/data/IQA
```

Local-only inputs may be staged into shared storage. Partial copies must never become
server-visible as completed inputs; SHA-256/content-addressed reuse is preferred
where practical.

The external server currently has a blocking HTTP interface. P5 targets a job API
with submit/status/result/cancel and polling as the initial progress mechanism.
WebSocket progress is not a P5 v1 requirement.

## UX direction

P5 adds one non-modal **IQA workspace/dock** rather than making a large custom modal
window the primary workflow.

```text
IQA
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
└─ Results
```

Native OS file/folder pickers may remain modal. Pair preparation, job progress, and
result exploration remain non-modal so users can continue ordinary PixelScope work.

### Current Pair

When two eligible native sources already form the current comparison context, IQA
Setup reuses them directly. The user should not browse for the same files again.

### Folder Pair

P5 v1 supports two-folder submission. PixelScope resolves and previews the same
sorted-by-index pair list before submission. Count mismatch disables submission;
semantic correctness of same-index matching remains the user's responsibility.

Large batch inputs remain IQA feature-local references and are not eagerly
Registered/Selected/decoded.

### Results

Result exploration follows:

```text
Job / dataset
    ↓
10-attribute overview
    ↓
selected attribute trend / outliers
    ↓
selected scene
    ↓
spatial grid comparison
    ↓
block inspector
```

The overview should support an Attribute × Scene matrix plus selected-attribute
trend/outlier navigation. The two official aggregation methods must be explicitly
selectable/labeled.

Passive result browsing must not mutate the current PixelScope Selected workspace.
An explicit **Inspect Pair** action loads only the chosen Scene pair through the
existing canonical registration/selection path. IQA Reference is separate from
PixelScope Primary. Inspection may keep a transient return point for the prior local
workspace; it is not Session persistence.

## Program sequence

`P5-0 → P5-A → P5-B → P5-C → P5-D → P5-E → P5-F → P5 Complete`

| Order | Slice | Status |
|---|---|---|
| 0 | P5-0 P4 Closure & P5 Program Setup | Active |
| 1 | P5-A Contract Fixtures & IQA Domain | Planned |
| 2 | P5-B IQA Workspace & Local Result Exploration | Planned |
| 3 | P5-C Submission & Shared Storage | Planned |
| 4 | P5-D Viewer-linked Scene Inspection | Planned |
| 5 | P5-E Historical Result Workflow | Planned |
| 6 | P5-F Integration & Performance Hardening | Planned |

## P5-0 — P4 Closure & P5 Program Setup — Active

### Goal

Close P4 documentation against merged PR #35 and establish the implementation
contract for P5 before runtime/UI work begins.

### Deliverables

- archive the completed P4 execution plan;
- update ROADMAP/CURRENT_STATE/UI status to P4 Complete / P5 Active;
- establish this P5 active execution plan;
- establish the Remote IQA durable contract;
- record the planned phase sequence and validation/review workflow;
- add no runtime/UI behavior and change no Settings/Session schema.

### Validation

P5-0 is docs-only. Run documentation/link validation and `git diff --check`; do not
claim runtime pytest/Ruff/mypy PASS from unchanged code unless actually rerun.

## P5-A — Contract Fixtures & IQA Domain

### Goal

Make the intended GPU contract executable and reviewable without a live server.

### Required implementation

- versioned Qt-free IQA domain schemas for Job/Scene/Source/Attribute/result metadata;
- result manifest + summary + compact scene artifact parser;
- deterministic mock server/result generator using the same production-shaped
  contract;
- local comparison/statistics utilities that reproduce fixture-authoritative values;
- corruption/missing-artifact/error models without UI dependency.

### Deterministic sample

Generate roughly 10–12 scenes × 2 sources with all ten attributes. The fixture must
be intentionally structured to include:

- visible dataset trends and spatial outliers;
- positive/negative/near-zero directional results;
- signed bias crossing negative/zero/positive;
- a case where the two official aggregation methods differ;
- local recomputation from compact source values/sufficient statistics matching the
  fixture's official server statistics;
- server-driven grid metadata including a non-default variant proving 32/128 are not
  hard-coded;
- non-zero grid origin, discarded border, and source→analysis transform;
- soft-weight and hard-gate provenance variants;
- identical-source, near-zero power, mismatch, missing/corrupt scene, and optional
  detail-artifact cases.

Large production-size 2K pixel arrays are not committed as fixtures.

### Acceptance

With no GPU server and no network, tests can parse the mock result, select either
official aggregation mode, derive scene/grid comparisons, and validate all geometry
and edge cases deterministically.

## P5-B — IQA Workspace & Local Result Exploration

### Goal

Prove the result UX against deterministic fixtures before server submission is added.

### Scope

- non-modal IQA dock/workspace skeleton;
- Open IQA Result... from a local/shared fixture artifact;
- Job/dataset overview;
- Attribute × Scene overview visualization;
- selected-attribute trend and outlier navigation;
- aggregation-mode selection;
- no passive mutation of Files/Selected/local analysis state;
- clean close/recreate lifecycle.

No live HTTP submission is required in P5-B.

## P5-C — Submission & Shared Storage

### Goal

Connect the proven result model/UX to the external service.

### Scope

- logical storage-root mapping;
- safe shared staging where required;
- Current Pair submission that reuses the current PixelScope pair;
- two-folder Setup with deterministic Pair Preview and count-mismatch blocking;
- explicit Scene manifest request;
- HTTP job submit/status/result/cancel adapter;
- polling progress with non-modal Jobs UI;
- result handoff to the same P5-B repository/parser path;
- retry/failure/cancel behavior without mutating the local image workspace.

The server implementation remains outside this repository.

## P5-D — Viewer-linked Scene Inspection

### Goal

Connect result anomalies to actual source-image locations without creating a new image
viewer or source authority.

### Scope

- explicit Inspect Pair action;
- canonical registration/selection of only the inspected pair;
- transient Return-to-previous-workspace behavior;
- IQA Reference state separate from Primary;
- scene navigation linked to the existing viewer after Inspect begins;
- remote-grid → analysis → source → viewer coordinate transform;
- vector/grid overlay using compact spatial result data;
- block inspector showing source values, raw comparison, semantic direction, and
  geometry;
- source mismatch/missing-source graceful degradation;
- no interference with native Difference/ROI/Line/Gain semantics.

P5-D must define safe behavior around an active P4-A temporary curation baseline;
v1 should block conflicting Inspect entry rather than silently invalidating Picks.

## P5-E — Historical Result Workflow

### Goal

Make remote IQA results reusable engineering records rather than one-shot job output.

### Scope

- Open IQA Result... durable workflow;
- bounded Recent IQA Results history;
- immutable result identity using job/result ID + logical path + source hashes;
- result-only mode when original sources are unavailable;
- source/hash mismatch diagnostics;
- job/purpose/project provenance presentation where available;
- evaluate whether Session should persist only a result reference + selected
  attribute/scene intent; do not embed remote arrays into Session.

Authentication/SSO/token/permission/admin operations remain P6.

## P5-F — Integration & Performance Hardening

### Goal

Validate the composed P5 workflow with the real server and large datasets while
preserving all inherited resource/lifetime contracts.

### Scope

- real external server compatibility against the versioned contract;
- large-result lazy loading and bounded local cache characterization;
- SMB/network bandwidth behavior;
- current-pair and large-folder submission stress;
- cancellation, server failure, missing artifacts, and application close/recreate;
- no eager loading of all scene/source data;
- no accidental Files/Selected/source residency ownership from batch membership;
- polling/task teardown and stale-result rejection;
- optional detail-artifact path characterization without making 2K maps mandatory;
- durable documentation and P5 closure.

No fixed wall-clock latency is a correctness merge gate. Deterministic gates are
bounded ownership, correct result identity, lazy loading, no duplicate submission or
analysis work, stale callback rejection, and teardown safety.

## Review workflow

Each P5 slice follows the established implementation/review loop:

1. implementation agent reads latest `main`, this plan, the Remote IQA contract, and
   relevant inherited durable docs;
2. work is kept to the named slice and committed in intentional subunits;
3. owner runs the required local Windows validation for runtime/UI work;
4. a PR is opened with goals, implementation summary, contracts preserved,
   validation evidence, and exclusions;
5. an independent reviewer checks the full latest branch against ROADMAP/contract,
   architecture/runtime integration, tests, resource ownership, and durable docs;
6. implementation agent addresses actionable review comments with additional focused
   commits;
7. latest head is re-reviewed before merge when blockers were found.

Reviewers should treat accidental changes to P2/P3/P4 source, selection, Difference,
Session, worker, preload, or residency authority as merge blockers unless the active
P5 slice explicitly and durably redesigns that contract.

## Validation policy

### Docs-only slices

Run:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
git diff --check
```

`tests/unit/test_docs_contract.py` may also be run when convenient. Full runtime
validation is not required solely because Markdown changed.

### Runtime/UI slices

Implementation agents should not waste time bootstrapping an unknown local virtual
environment. The repository owner performs Windows validation using the existing
`.venv`.

Use focused tests for the changed slice first, then the repository-standard checks
before merge as appropriate:

```powershell
.\.venv\Scripts\python.exe -m pytest -q <focused tests>
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Only observed results are recorded as PASS.

## Explicit exclusions from P5

P5 does not implement:

- GPU IQA model/training/server internals in this repository;
- P6 login/SSO/token/permission/admin lifecycle;
- Saved/named/multiple ROI deferred from P4;
- Alpha Overlay/Flicker/Wipe deferred from P4;
- arbitrary-angle Line Profile;
- RAW demosaic/WB/CCM/tone mapping;
- source-residency/preload redesign unrelated to measured P5 needs;
- packaging/signing/updater/release engineering owned by P7.