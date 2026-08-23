# P5-F — Remote IQA Integration & Performance Characterization

Status: **Active — implementation/characterization merge candidate; owner local validation pending**

Implementation base: `main@6a0a334d61a7495b9c3433edfcbd537c8df59468`

P5-F is the final Remote IQA integration/hardening slice. It consumes the merged
P5-A/A2/B/C/D/E authorities without changing IQA numerical meaning, Result publication
identity, local Files/Selected/residency ownership, or Session v1.

## 1. Evidence boundary

This document separates repository-observed facts from environment-dependent validation.

Observed in the implementation/architecture review:

- P5-B Result open and Reference preparation, P5-D source verification/spatial loading,
  and P5-E logical Recent resolution were all scheduled on the same max-two application
  analysis pool whose established owner is local Statistics/Difference work.
- `HttpIqaJobClient` owns an `httpx.Client` and can reuse its connection pool while the
  client remains alive, but production P5-C composition created and closed a client for
  each individual create/status/result/cancel operation.
- schema-v2 Reference preparation already holds one Scene grid at a time and retains
  derived relative scalar results, not a raw dataset-wide grid corpus. Re-selecting an
  already prepared Reference returns the prepared model without rereading all grids.
- hashing and staging remain streaming/bounded P5-C operations; P5-F does not make a
  submitted or historical batch a second source-residency owner.

Not observed by this implementation agent:

- no real external GPU server was available;
- no production SMB share was available for timing characterization;
- no owner Windows `.venv` validation was run by this agent;
- no wall-clock performance number is therefore recorded as a PASS threshold.

The repository owner explicitly deferred real GPU/SMB validation and will run local
validation separately. No GitHub Actions or new CI workflow is introduced by P5-F.

## 2. Measured/structural findings and retained corrections

### 2.1 Remote IQA versus local analysis executor contention

**Observed architecture before P5-F**

The P5-B/P5-D/P5-E file/grid operations used `analysis_thread_pool()`, a max-two pool
whose documented role is local full-frame Statistics/Difference work. Slow SMB I/O can
be advisory-cancelled yet remain physically blocked, so two such operations can occupy
both local-analysis slots.

**Correction**

P5-F adds one application-owned Remote IQA pool with fixed concurrency `2` and rebinds
only the existing P5-B Result/Reference, P5-D verification/spatial, and P5-E historical
resolver controllers at the production composition boundary.

It does not create a new Result parser, explorer, source registry, source loader,
residency manager, or numerical authority. Existing generation/stale-result rejection
continues to apply.

**Structural evidence added**

A blocking-I/O regression saturates both Remote IQA workers and verifies an unrelated
local analysis worker can still execute on the separate Statistics/Difference pool.
The test asserts pool identity/concurrency rather than a fragile latency target.

### 2.2 HTTP client lifetime

**Observed architecture before P5-F**

The P5-C helper functions correctly close their supplied client after each operation,
but the production factory supplied a newly constructed `HttpIqaJobClient` every time.
The underlying `httpx.Client` connection pool therefore could not survive across job
lifecycle requests.

**Correction**

P5-F injects a bounded `ReusableIqaClientPool` through the already-existing P5-C
`client_factory` seam:

- one lease is owned by one worker operation;
- an underlying client is never concurrently shared between worker threads;
- at most two idle endpoint clients are retained globally;
- returning a lease may reuse the underlying `httpx.Client`/keep-alive pool;
- window close closes idle clients but never cancels a durable remote job;
- a client still leased to a running worker is not closed underneath that worker and is
  closed when returned after shutdown.

No CREATE retry, polling cadence, result-reference semantics, or cancel race semantics
change.

**Structural evidence added**

Unit regressions cover idle reuse, same-endpoint concurrent isolation, idle retention
bounds, discard/close behavior, and shutdown with an active lease.

## 3. Protocol compatibility probe

`pixelscope.remote.iqa_compatibility_probe` provides a bounded client-side probe for the
frozen P5-C endpoints:

- `POST /v1/iqa/jobs`
- `GET /v1/iqa/jobs/{job_id}`
- `GET /v1/iqa/jobs/{job_id}/result`
- `POST /v1/iqa/jobs/{job_id}/cancel`

The probe records only bounded protocol metadata:

- state sequence;
- Scene progress;
- operation timing observations;
- terminal state;
- Result schema/publication/logical-reference metadata;
- classified error kind/status.

CREATE is called exactly once. Status calls are serial. Optional cancel is a single
bounded operation. The trace excludes the server URL, request body, credentials, source
content, and detailed transport exception text.

Developer entry point:

```powershell
.\.venv\Scripts\python.exe scripts\p5f_iqa_probe.py `
    <server-base-url> <request.json>
```

This command is prepared for later owner/live-server use; no live-server PASS is claimed
in this PR.

## 4. Result / Reference / grid characterization path

`scripts/p5f_result_characterize.py` reads an already-published schema-v2 Result through
the canonical parser and reports observations separately for:

- canonical Result open;
- manifest read bytes/time;
- full summary NPZ array read bytes/time;
- first Reference preparation;
- repeated prepared Reference;
- a different Reference when available;
- first Scene grid load;
- declared grid uncompressed size;
- actual retained ndarray bytes for that grid.

It does not write the Result or add a cache. It intentionally distinguishes declared
artifact size from retained decompressed array memory.

Developer entry point:

```powershell
.\.venv\Scripts\python.exe scripts\p5f_result_characterize.py <result-root>
```

Real mapped-share timing remains an owner observation, not a repository correctness
threshold.

## 5. Diagnostics

P5-F extends the existing immutable **Help > Copy Diagnostics** snapshot rather than
creating a second diagnostics UI/framework.

The optional Remote IQA section contains bounded counters only:

- active/max Remote IQA worker count;
- HTTP clients created;
- HTTP leases reused;
- active/max-active leases;
- idle clients;
- discarded clients;
- transport closed state.

No HTTP body, source path, credential, image array, or per-Scene unbounded timing history
is retained.

## 6. Representative workload coverage

P5-F adds generated in-memory request-structure coverage for:

- 1 Scene;
- 10 Scenes;
- 50 Scenes;
- 150 Scenes;
- 300 Scenes.

These tests assert deterministic Scene IDs and A/B variant order without committing
large binary fixtures. Existing P5-C limits still cap requests at 512 Scenes.

The existing P5-A2/B/C/D/E suites remain regression authority for schema safety,
summary-first Result opening, PARTIAL, storage streaming/dedupe, source verification,
Inspect/Return, stale callbacks, Recent remap/identity, and v1 read-only compatibility.
P5-F does not copy those contracts into a parallel implementation.

## 7. Memory/resource invariants

P5-F retains these bounds:

- Remote IQA file/grid executor: fixed max 2 threads;
- P5-C job-operation executor: existing fixed max 2 threads, unchanged;
- reusable HTTP transport: max 2 idle clients;
- raw-grid cache: none;
- grid preload: none;
- source-residency ownership: unchanged;
- Difference cache: unchanged and independent;
- staging/hashing: existing streaming implementation;
- optional detail artifacts: not loaded by P5-F.

Remote batch membership, Result Scene membership, and Recent history still do not protect
native source memory. Only explicit P5-D Inspect enters the canonical local source
lifecycle.

## 8. Optimizations considered but deliberately not implemented

### Raw-grid cache

Not implemented. Current P5-B keeps derived scalar Reference results and processes one
Scene grid at a time. Without real mapped-share evidence of materially harmful repeated
grid reads, a second raw-grid memory owner is not justified.

### Adjacent Scene/grid preload

Not implemented. No measured access-pattern evidence justifies speculative grid I/O, and
P5-F must not compete with foreground native source work merely to anticipate navigation.

### Adaptive polling/backoff

Not implemented. The existing fixed polling cadence remains, with one poll in flight per
job. No real-server request-volume evidence was available to justify changing UX or
cadence semantics.

### Generalized HTTP retry

Not implemented. CREATE remains non-idempotent/outcome-ambiguous and is never blindly
retried. Existing P5-C result-reference recovery behavior remains authoritative; P5-F
does not turn protocol/schema corruption into a transient retry.

### New performance Settings

Not implemented. Worker count, polling cadence, retry count, or cache budget are not
promoted to permanent user product contracts without a demonstrated need.

### Optional detail-artifact viewer

Deferred. Without actual server output demonstrating a stable typed kind/dtype/shape/
geometry contract and a clear product need, filename conventions do not establish a
safe consumer contract. Mandatory schema-v2 grid spatial inspection already exists.

## 9. Validation status

### Added P5-F focused test files

```text
tests/unit/test_p5f_transport_pool.py
tests/unit/test_p5f_compatibility_probe.py
tests/unit/test_p5f_diagnostics.py
tests/ui/test_p5f_worker_isolation.py
```

The implementation agent did **not** execute the repository `.venv` gate. These tests and
the inherited full suite are **pending owner local validation**. No PASS count is claimed.

Recommended owner-local focused start:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\unit\test_p5f_transport_pool.py `
    tests\unit\test_p5f_compatibility_probe.py `
    tests\unit\test_p5f_diagnostics.py `
    tests\ui\test_p5f_worker_isolation.py `
    -q
```

Then run the repository-standard validation locally when appropriate. P5-F does not add
or require GitHub Actions for this purpose.

## 10. Deferred owner real GPU / SMB matrix

When the environment becomes available, record observations for:

- Current Pair submit → COMPLETE → Open Result → Reference → Inspect/spatial;
- Folder Pair with 10–20 Scenes and deterministic order/progress;
- PARTIAL successful/failed-or-cancelled Scene mix;
- early and late cancel/publication race;
- Recent historical reopen and root remap;
- shared-root source, staged source, staging dedupe, mapped Result open;
- concurrent local Statistics/Difference/Display Gain/ROI/Line/page navigation;
- close/reopen and rapid Result/Scene changes.

Record client head SHA, server build/algorithm identifiers when available, approximate
Scene/source count, storage topology, and observed timings. Do not convert those timing
observations into correctness thresholds unless a concrete regression is later frozen.

## 11. P5 closure

This branch prepares P5 closure but does **not** mark P5-F or P5 Complete while the PR is
unmerged.

After review, owner local validation, any later required real-server validation, and
merge, a tiny docs-only closeout should:

1. record the actual P5-F merge SHA;
2. mark P5-F Complete;
3. mark P5 Remote IQA Platform Complete;
4. archive the active P5 plan under `docs/exec-plans/completed/`;
5. make P6 **Identity, Access & Remote Operations** the active/next program.

P6/P7 implementation is outside this branch.
