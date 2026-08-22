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

Observed evidence and planned validation are always separate. PASS on an older head
is historical evidence, not automatic validation of a later head.

## Goal and inherited authority

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
```

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

P5-B merged at `a44978db783ebcecb0d55f8abb52b583e0fdc47c` and remains the
canonical Open IQA Result / Results UI authority reused by P5-C.

## P5-C implementation status

### C1 — machine-local logical storage configuration — Complete

Application settings schema v6 owns `RemoteIqaSettings` with server URL, logical
storage-root mappings, and staging-root selection. `storage_root_id + relative_path`
is portable identity. Client paths, server physical paths, and credentials are not
portable request/result identity and Session v1 does not own them.

### C2 — initial submission identity — Complete

The initial user-facing request is exactly two variants `A/B`.

- Current Pair is the A/B pair of underlying Current Comparison Page documents.
- Primary, Active, viewer reorder, Display Gain, Difference, and Split do not redefine
  that source order.
- Folder Pair uses immediate PNG/JPG/JPEG/BMP files only, no recursion or symlinks,
  NFC lexical ordering, equal eligible count, pair-by-index ordering, equal dimensions,
  deterministic Scene IDs, and a 512-Scene bound.
- Folder Pair remains feature-local and does not register the batch or acquire
  Files/Selected/current-page/residency/preload authority.

### C3 — shared storage/staging — Complete / hardened

Implementation now provides:

- most-specific logical-root resolution;
- streaming SHA-256;
- content-addressed `staging/<sha256>/<basename>` for outside-root inputs;
- unique same-directory temporary publication rather than one shared `.part` name;
- resolved containment before child filesystem mutation;
- rejection of source/result symlink or junction escapes outside the logical root;
- atomic final publication with SHA-256 verified winner/reuse semantics, including
  the Windows concurrent `os.replace()` race.

Focused concurrency/containment regressions cover these contracts.

### C4 — job API/client lifecycle — Complete / hardened

API remains:

```text
POST /v1/iqa/jobs
GET  /v1/iqa/jobs/{job_id}
GET  /v1/iqa/jobs/{job_id}/result
POST /v1/iqa/jobs/{job_id}/cancel
```

Implemented lifecycle rules:

- create POST is one-shot and never blindly auto-retried;
- one local in-flight preparation/create owner prevents duplicate submission;
- timeout/connect-loss/5xx/unusable success after create are treated as ambiguous
  outcomes and block further submission in that PixelScope process rather than
  inviting a duplicate retry;
- server-returned job IDs use the same bounded path-segment validation as later calls;
- cooperative cancellation reaches folder enumeration, image probing, hash chunks,
  staging copy/path work, and a final checkpoint immediately before create POST;
- local shutdown does not remotely cancel durable jobs;
- terminal result-reference acquisition has bounded idempotent 1s/2s/4s/8s recovery;
- result completion never auto-opens Results; explicit Open Result delegates to P5-B;
- storage-root mapping changes use revision + pending re-resolution so stale
  old-settings callbacks cannot overwrite the newest mapping.

### C5 — executable PARTIAL schema-v2 — Complete

P5-C extends schema v2 without a schema bump. Ordered `scene_outcomes[]` covers every
requested Scene; successful Scenes retain normal v2 numerical/geometry invariants;
PARTIAL requires at least one success and at least one failure/cancellation; zero
success publishes no PARTIAL result; all success is COMPLETE.

### C6 — single IQA workspace composition — Complete

One non-modal IQA dock contains Setup / Jobs / Results. Results is the merged P5-B
workspace, not a new parser/controller.

### C7 — debug contract harness — Complete

`PIXELSCOPE_REMOTE_IQA_DEBUG` gates Request Inspector, Replay JSON, deterministic
COMPLETE/PARTIAL result fixtures, and the real-socket localhost fault server. These
validate the client contract and are not production server architecture.

### C8 — independent-review closeout — Implemented, validation pending

Independent whole-PR review at `177078fb65da2bfb0be50391f27015b5e955a3c2`
confirmed the earlier P5-C architecture blockers closed and requested three narrow
merge-closeout items:

1. prevent Folder Pair validation from leaving `Validate / Preview` permanently
   disabled when the inputs change while an older validation is still running;
2. add explicit production-composition regressions proving Current Pair A/B authority
   survives Primary/Active/presentation reorder and Folder Pair preparation does not
   mutate Files/Selected/current page/residency/preload;
3. reconcile durable status text that still described completed hardening as future
   work.

The runtime/test portion is implemented by `70b7b6d39599077e2ebbad86d34b1baedc741910`:

- latest-preview revision/worker ownership rejects stale preview callbacks and
  restores Validate after the latest worker finishes;
- Current Pair page-order authority regression added;
- Folder Pair local-authority isolation regression added.

No PASS is claimed yet for that closeout head. Reviewer optimization recommendations
such as HTTP connection reuse, status-error backoff, retryability-aware `/result`
retries, debug replay collision handling, hash/stage caching, and timer optimization
are explicitly deferred beyond this P5-C merge closeout.

## Observed validation evidence

Only observed evidence is authoritative.

- historical full checkpoint `04f8c08...`: 809 pytest PASS plus Ruff/mypy/diff PASS;
- owner full requested validation on durable-doc head `f7728b2...`: PASS;
- Stage-4 localhost/result-retry/submission/UI focused suite: 26 PASS;
- real-socket normal create → poll → result-reference manual flow: PASS;
- repeated first-terminal-`GET /result` HTTP 500 then bounded recovery without
  resubmission: PASS;
- staging hardening focused suite through `63ecdcd...`: 17 PASS plus Ruff/mypy/diff;
- lifecycle/storage hardening after Windows publication-race repair: owner reported
  the complete requested focused/static gate PASS;
- result-remap focused tests, Ruff check, mypy, and `git diff --check` on `86cc871...`:
  PASS; `177078f...` was the subsequent formatter-only repair.

The new closeout implementation/docs require current-head focused/static validation.
Do not carry older full PASS forward.

## P5-C remaining execution order

### Steps 1–4 — Complete

The earlier durable-doc, staging-safety, create/shutdown, and settings-remap blocker
stages are implemented. Their contracts remain frozen; do not reopen P5-A2 math or
P2 residency/preload design during closeout.

### Step 5 — reviewer closeout fixes — Active

Complete the narrow independent-review requests:

- Folder Pair stale-preview lifecycle fix;
- Current Pair A/B presentation-independence regression;
- Folder Pair Files/Selected/current-page/residency/preload isolation regression;
- stale durable status/evidence reconciliation.

### Step 6 — focused/static owner validation

After the closeout code/docs head is ready:

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

Ask the independent reviewer to inspect the latest head specifically against the
three closeout findings and confirm that no new merge blocker was introduced.
Any blocker returns to implementation → focused validation → fresh review.

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
- record the final merge SHA and move the active P5 plan forward.

## P5-D — blocked until P5-C closes

P5-D will own viewer-linked Scene/source/spatial inspection. It must not start on
PR #42 or before P5-C merge.

## P5-E / P5-F — planned

P5-E owns historical result productivity such as bounded Recent IQA Results and
production historical reopen. P5-F owns real-server integration and measured
performance hardening, including network/session reuse, retry/backoff tuning,
shared-storage performance characterization, and stress/failure/cancellation work.
Authentication remains P6; packaging/signing/updater remains P7.
