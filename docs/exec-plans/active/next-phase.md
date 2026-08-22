# Execution plan: P5 — Remote IQA Platform

Status: Active — **P5-C Submission & Shared Storage / Draft PR #42 closeout**
Owner: repository owner + P5 orchestrator + slice implementation/review agents
Last updated: 2026-08-23
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
| P5-C | **Active — Draft PR #42 closeout** | submission/shared storage/jobs/PARTIAL |

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
- equal eligible count;
- pair sorted entries by index;
- exact original dimensions per pair;
- 1..512 Scenes.

Request Scene IDs are `scene_000000...`. Each Scene serializes A then B. Portable
source identity contains logical root, relative path, SHA-256, width, and height.

Arbitrary 3+ variant submission UI remains outside P5-C. Externally produced N-way v2
results remain supported by P5-B.

### C3 — shared storage/staging — implemented/hardened

Current implementation:

- most-specific matching logical root resolves an existing source;
- SHA-256 is streamed;
- sources outside configured roots may be staged as
  `staging/<sha256>/<basename>`;
- independently named same-directory temp files prevent shared `.part` collisions;
- resolved containment is checked before child filesystem mutation;
- source/result symlink or junction escapes outside the configured logical root are
  rejected;
- atomic final publication/reuse is SHA-256 verified, including the Windows
  concurrent `os.replace()` loser case.

Focused regressions cover concurrent staging and symlink/junction containment where
the platform supports them.

### C4 — job API/client lifecycle — implemented/hardened

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
- one in-flight local preparation/create owner prevents duplicate in-process submit;
- ambiguous create outcomes block further submit in that process rather than
  inviting a blind retry;
- server-returned job ID must pass the same bounded path-segment validation used by
  later requests;
- only succeeded/partial may obtain a result reference;
- result reference must identify schema version 2 and complete/partial publication;
- terminal result-reference GET is recoverable with bounded 1s/2s/4s/8s backoff;
- retry exhaustion keeps the terminal job visible and never resubmits it;
- cooperative cancellation reaches preflight/hash/staging and checks again
  immediately before create POST;
- local shutdown does not remotely cancel already-created durable jobs;
- result completion never auto-opens Results;
- explicit Open Result resolves current machine-local logical mapping and delegates
  to P5-B;
- a storage-root mapping change during result-path resolution uses revision + pending
  re-resolution so the newest mapping wins.

Client errors are classified into configuration, connection, timeout, HTTP, protocol,
and storage-resolution categories.

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

### C8 — independent-review closeout — implemented, validation pending

Independent whole-PR review at `177078fb65da2bfb0be50391f27015b5e955a3c2`
confirmed the earlier runtime architecture blockers closed and requested three narrow
closeout items:

1. restore `Validate / Preview` after an in-flight Folder Pair validation becomes
   stale because Folder A/B changed;
2. add executable regressions for Current Pair A/B page-order authority and Folder
   Pair isolation from Files/Selected/current page/residency/preload;
3. reconcile stale durable status text that still described completed hardening as
   future work.

The runtime/test portion is implemented by
`70b7b6d39599077e2ebbad86d34b1baedc741910`. It installs latest-preview worker
ownership so stale callbacks cannot publish over a newer validation or permanently
strand Validate, plus both requested production-composition authority regressions.
Current-head validation is pending.

Reviewer optimization recommendations are deliberately deferred from this merge
closeout. Real-server HTTP/session reuse, polling/backoff tuning, retryability-aware
result-reference recovery, debug replay collision handling, hash/stage caching, and
idle-timer optimization belong to later measured P5-E/P5-F work unless promoted by a
future owner decision.

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

### Localhost/retry Stage 4 and later hardening

Owner observed:

- focused localhost/result-retry/submission/UI pytest: **26 passed**;
- normal real-socket submit → poll → result-reference flow PASS;
- first terminal `GET /result` returning HTTP 500 then automatic successful retry
  without resubmission PASS;
- the transient-result recovery was repeated with a second newly-created job and
  again ended `succeeded` with Open Result enabled;
- full requested validation on durable-doc head `f7728b2...`: PASS;
- staging and lifecycle/storage focused/static validation after the Windows
  concurrent-publication repair: PASS;
- result-remap focused tests, Ruff check, mypy, and `git diff --check` on
  `86cc871...`: PASS; `177078f...` is the following formatter-only repair.

The new reviewer-closeout code/docs head still requires focused/static owner
validation. Do not carry older full PASS forward.

## P5-C remaining execution order

### Steps 1–4 — Complete

The earlier durable-doc contract reconciliation, staging safety hardening,
create/shutdown lifecycle hardening, and settings-remap race hardening are complete.
They remain frozen and must not be reopened during closeout.

### Step 5 — reviewer closeout fixes — Active

Implement/reconcile:

- latest Folder Pair preview ownership and edit-during-validation recovery;
- Current Pair A/B presentation-independence regression;
- Folder Pair Files/Selected/current-page/residency/preload isolation regression;
- stale durable blocker/status text.

### Step 6 — focused/static owner validation

After the closeout head:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\ui\test_p5c_authority_closeout.py `
    tests\ui\test_p5c_remote_iqa.py `
    tests\ui\test_p5c_submission_lifecycle.py `
    tests\ui\test_p5c_result_mapping.py `
    -q

.\.venv\Scripts\python.exe -m ruff check `
    src\pixelscope\ui\iqa_preview_lifecycle.py `
    src\pixelscope\app\application.py `
    tests\ui\test_p5c_authority_closeout.py

.\.venv\Scripts\python.exe -m ruff format --check `
    src\pixelscope\ui\iqa_preview_lifecycle.py `
    src\pixelscope\app\application.py `
    tests\ui\test_p5c_authority_closeout.py

.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\check_docs.py
git diff --check
```

Do not claim PASS until owner output is observed.

### Step 7 — independent closeout re-review

Review the latest head against the three narrow closeout findings and confirm no new
merge blocker. Any blocker goes back to implementation → focused validation → fresh
review.

### Step 8 — final full repository gate

After independent PASS:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

### Step 9 — owner merge decision

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
- HTTP/session reuse and status/retry/backoff tuning where measurement justifies it;
- grid cache/preload/network characterization;
- stress/failure/cancellation;
- realistic reference-switch latency;
- optional detail artifact characterization;
- P5 closure documentation.

Authentication/SSO/tokens/permissions remain P6. Packaging/signing/updater remains P7.
