# Execution plan: P5 — Remote IQA Platform

Status: Active — **P5-C Submission & Shared Storage / Draft PR #42**
Owner: repository owner + P5 orchestrator + slice implementation/review agents
Last updated: 2026-08-22
Current merged main: `ad3721e28b759e75d8e0f4a28b003a4dd22f0f4a`

Authoritative P5 documents:

- product/transport/ownership contract:
  [`docs/REMOTE_IQA_CONTRACT.md`](../../REMOTE_IQA_CONTRACT.md)
- current numerical/result contract:
  [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)
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
- **Independent reviewers** inspect the latest full PR head against inherited
  contracts, tests, resource/lifetime rules, and docs without modifying the branch.
- **Repository owner** supplies unresolved policy decisions and runs requested local
  Windows validation.

Observed evidence and planned validation are always kept separate. A PASS from an
older head is historical evidence, not automatic validation of a later head.

## Goal

P5 connects PixelScope to an external GPU Image Quality Assessment service while
preserving PixelScope as a fast local comparison tool.

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
future explicit Scene/source/spatial inspection
```

The external GPU model/server lives outside this repository. PixelScope owns client
preparation, transport contract, portable storage identity, stable result parsing,
local reference-dependent exploration, and later viewer integration.

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

P5 must not create another authority for Files/Selected/Current Comparison Page,
source residency/protection/preload, Difference/cache, Display Gain, native analysis,
or Session v1.

## Completed P5 baseline

| Slice | Status | Authority |
|---|---|---|
| P5-0 | Complete — PR #36 | program setup/contracts |
| P5-A | Complete — PR #37 | historical executable schema v1 |
| P5-A2 Stage 1 | Complete — PR #39 | durable schema-v2 model |
| P5-A2 Stage 2 | Complete — PR #40 | executable schema-v2 reader/math/artifacts |
| P5-B | Complete — PR #38 | canonical local IQA Results workspace |
| P5-C | **Active — Draft PR #42** | submission/shared storage/jobs/PARTIAL |

P5-B merged at `a44978db783ebcecb0d55f8abb52b583e0fdc47c` and is the
canonical Open IQA Result / Results UI authority that P5-C reuses.

## Current executable schema-v2 contract

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 separates:

- `variant_id` — stable comparison/Reference slot identity;
- `source_id` — concrete source identity;
- `scene_id` — evaluation Scene;
- `measurement_context_id` — Scene measurement context.

Published successful Scenes retain complete variant/geometry/numerical invariants.
Server-authored W/S1/S2/count/valid remain measurement authority. PixelScope derives
pair-valid reference comparisons and uses the canonical v2 helpers rather than UI-
local math.

Schema v1 remains explicit read-only compatibility.

## P5-C — active scope

### C1 — machine-local logical storage configuration — frozen/implemented

Application settings schema v6 owns:

```text
RemoteIqaSettings
    server_base_url
    storage_roots[] {
        storage_root_id
        client_path
    }
    staging_root_id
```

Rules:

- `storage_root_id + relative_path` is portable identity;
- `client_path` is local drive/UNC configuration only;
- server physical paths and credentials are not persisted by PixelScope;
- Result artifacts and Session v1 do not own machine-local mappings.

### C2 — initial submission identity — frozen/implemented

Initial user-facing request cardinality is exactly two variants `A/B`.

Current Pair:

- A/B pair of underlying Current Comparison Page documents;
- exact original dimensions required;
- independent from Primary, Active, viewer reorder, Display Gain, Difference, and
  Split presentation.

Folder Pair:

- immediate eligible files only;
- no recursion;
- symlinks excluded;
- PNG/JPG/JPEG/BMP only;
- Unicode NFC + deterministic lexical order;
- equal eligible counts;
- pair sorted entries by index;
- exact original dimensions per pair;
- 1..512 Scenes.

Request Scene IDs are `scene_000000...`. Each Scene serializes A then B. Portable
source identity contains logical root, relative path, SHA-256, width, and height.

Arbitrary 3+ variant submission UI remains outside P5-C. Externally produced N-way v2
results remain supported by P5-B.

### C3 — shared storage/staging — implemented, hardening still required

Current implementation:

- most-specific matching logical root resolves an existing source;
- SHA-256 is streamed;
- sources outside configured roots may be staged as
  `staging/<sha256>/<basename>`;
- `.part` publication and atomic replace/reuse verification are used;
- staging does not intentionally mutate Files/Selected.

Before merge, fix and test:

1. cross-process/concurrent staging of the same target;
2. resolved containment before filesystem mutation;
3. source symlink/junction boundary so logical identity cannot disagree with the
   resolved physical source.

### C4 — job API/client lifecycle — implemented, closeout hardening required

API:

```text
POST /v1/iqa/jobs
GET  /v1/iqa/jobs/{job_id}
GET  /v1/iqa/jobs/{job_id}/result
POST /v1/iqa/jobs/{job_id}/cancel
```

States:

```text
queued
preparing
extracting
aggregating
writing
succeeded
partial
failed
cancelled
```

Polling is initial progress transport. WebSocket is not required.

Rules:

- create POST is never automatically retried;
- server-returned job ID must pass the same bounded path-segment validation used by
  later requests;
- only succeeded/partial may obtain a result reference;
- result reference must identify schema version 2 and complete/partial publication;
- terminal result-reference GET is recoverable with bounded 1s/2s/4s/8s backoff;
- retry exhaustion keeps the terminal job visible and never resubmits it;
- result completion never auto-opens Results;
- explicit Open Result resolves current machine-local logical mapping and delegates
  to P5-B.

Client errors are classified into configuration, connection, timeout, HTTP, protocol,
and storage-resolution categories.

Before merge, resolve:

1. duplicate in-process submission while preparation/create is already in flight;
2. ambiguous create when timeout/error occurs after the server may have accepted POST;
3. cooperative cancellation/shutdown checkpoints before create POST;
4. running worker close/recreate safety.

### C5 — executable PARTIAL schema-v2 — frozen/implemented

P5-C extends schema v2 without a schema bump.

A valid PARTIAL result:

- has `publication_state = "partial"`;
- has ordered `scene_outcomes[]` covering every requested Scene;
- each outcome is succeeded, failed, or cancelled;
- succeeded has no error diagnostics;
- failed/cancelled requires bounded error code/message and may include boolean
  `retryable`;
- has at least one success and at least one failed/cancelled Scene;
- stores only fully published successful Scenes in `scenes[]`, in the exact success
  order from `scene_outcomes`;
- applies the same complete-Scene schema-v2 numerical/geometry/cardinality rules to
  each successful Scene;
- treats zero-success as FAILED/CANCELLED with no result reference;
- treats all-success as SUCCEEDED/COMPLETE.

P5-B Results displays partial progress/diagnostics and explores successful Scenes.

### C6 — single IQA workspace composition — implemented

One non-modal IQA dock:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

Setup owns submission configuration/pair preparation. Jobs owns tracked job state,
Cancel, and explicit Open Result. Results is the merged P5-B workspace, not a new
parser/controller.

### C7 — debug contract harness — implemented

Debug-only opt-in:

```text
PIXELSCOPE_REMOTE_IQA_DEBUG
```

Harnesses:

- Request Inspector — production request preparation without POST;
- Replay JSON — bounded logical terminal job/result injection without HTTP;
- deterministic COMPLETE/PARTIAL result generator using the canonical v2 fixture
  writer and loader;
- real-socket localhost fault server using stdlib `ThreadingHTTPServer`.

The localhost server intentionally returns references to deterministic existing fake
schema-v2 results rather than implementing GPU IQA. It validates the production HTTP
client contract until a real server adapter exists.

## Current observed P5-C validation

Only observed evidence is authoritative.

### Historical full checkpoint

At `04f8c08...`:

- full `pytest -q`: 809 PASS;
- Ruff/mypy/diff checks: PASS.

This predates later P5-C stages and is not current-head validation.

### Setup / Request Inspector

Owner validated focused behavior and static checks through `41384ec...`.

### Replay/fake result harness

Owner validated the repaired Stage-3 flow through `444391d...`:

- focused replay tests PASS;
- deterministic COMPLETE generation PASS;
- Jobs replay injection PASS;
- no automatic Open Result;
- explicit Open Result through P5-B PASS.

### Localhost/retry Stage 4

Owner observed:

- focused localhost/result-retry/submission/UI pytest: **26 passed**;
- mypy `src`: **102 source files, no issues**;
- normal real-socket submit → poll → result-reference flow PASS;
- first terminal `GET /result` returning HTTP 500 then automatic successful retry
  without resubmission PASS;
- the transient-result recovery was repeated with a second newly-created job and
  again ended `succeeded` with Open Result enabled.

The latest-head static/full gate remains pending. Do not carry older full PASS forward.

## P5-C remaining execution order

Proceed in this order:

### Step 1 — durable docs reconciliation — Active

Reconcile current implementation and remaining blockers across:

- `REMOTE_IQA_CONTRACT.md`;
- `REMOTE_IQA_V2_SPEC.md`;
- `CURRENT_STATE.md`;
- `ROADMAP.md`;
- this active plan;
- `ARCHITECTURE.md`;
- `DECISIONS.md`;
- `QUALITY.md`;
- `PRODUCT_SPEC.md`;
- `USER_GUIDE.md`;
- UI status/index only where necessary.

`REMOTE_IQA_V1_SPEC.md` remains historical and unchanged.

### Step 2 — staging safety hardening

Implement/test:

- unique or otherwise concurrency-safe staging temporary publication;
- containment before mutation;
- source symlink/junction resolved containment;
- concurrent staging regression where platform permits.

### Step 3 — create/shutdown lifecycle hardening

Implement/test:

- duplicate in-flight submit prevention;
- explicit ambiguous-create state/UX or a frozen idempotency mechanism;
- cooperative cancellation during preflight/hash/staging;
- cancellation checkpoint immediately before create POST;
- running-worker shutdown/close-recreate regression.

Do **not** add blind create POST retry.

### Step 4 — settings remap race hardening

When Remote IQA root mapping changes during result-path resolution, ensure the newest
settings revision wins after the in-flight resolver completes. Add a deterministic
regression.

### Step 5 — focused/static owner validation

After blocker fixes:

```powershell
.\.venv\Scripts\python.exe -m pytest -q <focused P5-C suites>
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
git diff --check
```

Do not claim PASS until owner output is observed.

### Step 6 — final full repository gate

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

### Step 7 — independent latest-head whole-PR review

Review architecture, lifecycle, storage safety, tests, durable docs, inherited
P2/P3/P4 authorities, and P5-A2/P5-B numerical/result ownership.

Any blocker goes back to implementation → focused validation → fresh review.

### Step 8 — owner merge decision

Only after final validation and independent PASS:

- update PR #42 from Draft when appropriate;
- merge P5-C only with owner approval;
- record final merge SHA and move plan/state forward.

## P5-D — blocked until P5-C closes

P5-D will own viewer-linked Scene/source/spatial inspection:

- logical-root + source-hash verified native Inspect;
- canonical registration/selection of chosen Scene sources only;
- P4-A Pick-state conflict guard;
- Scene/grid → source/viewer coordinate mapping;
- spatial overlay/block inspection;
- transient return semantics.

P5-D must not start on PR #42 or before P5-C merge.

## P5-E — planned

Historical result productivity:

- bounded Recent IQA Results;
- production historical reopen;
- result-only mode;
- source/hash diagnostics;
- provenance display.

Session v1 remains unchanged unless a later explicit Session schema revision is made.

## P5-F — planned

Final real-server integration and measured performance hardening:

- external server compatibility;
- real shared storage/SMB behavior;
- grid cache/preload/network characterization;
- stress/failure/cancellation;
- realistic reference-switch latency;
- optional detail artifact characterization;
- P5 closure documentation.

Authentication/SSO/tokens/permissions remain P6. Packaging/signing/updater remains P7.
