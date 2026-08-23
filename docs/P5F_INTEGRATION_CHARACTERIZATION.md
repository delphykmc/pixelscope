# P5-F — Remote IQA Integration & Performance Characterization

Status: **Active — implementation review passed and merge validation disposition recorded**

Implementation base: `main@6a0a334d61a7495b9c3433edfcbd537c8df59468`

P5-F is the repository-side Remote IQA integration/hardening slice. It consumes the
merged P5-A/A2/B/C/D/E authorities without changing IQA numerical meaning, Result
publication identity, local Files/Selected/residency ownership, or Session v1.

Real external GPU/SMB validation is deliberately separated into **P5-G — External
GPU/SMB Validation & Closeout** because that environment is currently unavailable.
Merging P5-F must not mark the overall P5 program Complete.

## 1. Evidence boundary

This document separates repository-observed facts, owner-local validation, and
unobserved external-environment validation.

Observed in implementation/architecture review:

- P5-B Result open and Reference preparation, P5-D source verification/spatial loading,
  and P5-E logical Recent resolution were all scheduled on the same max-two application
  analysis pool whose established owner is local Statistics/Difference work.
- `HttpIqaJobClient` owns an `httpx.Client` and can reuse its connection pool while the
  client remains alive, but production P5-C composition created/closed a client around
  each individual create/status/result/cancel operation.
- the first P5-F reusable-client implementation still acquired physical clients before
  P5-C workers entered the max-two job pool. Independent review identified that queued
  operations could therefore exceed physical worker concurrency and a queued worker
  removed by `QThreadPool.clear()` could miss the helper `finally: close()` path.
- schema-v2 Reference preparation already holds one Scene grid at a time and retains
  derived relative scalar results, not a raw dataset-wide grid corpus. Re-selecting an
  already prepared Reference returns the prepared model without rereading all grids.
- hashing and staging remain streaming/bounded P5-C operations; P5-F does not make a
  submitted or historical batch a second source-residency owner.

Owner-local validation evidence:

- implementation head `f9a81b008d660405fc01e775607d78a91676093e` passes the focused P5-F
  suite, docs checker, Ruff check/format, mypy, pip check, and `git diff --check`;
- full Windows offscreen pytest on that head reports 925 passed, 1 skipped, and the
  same three Qt/pyqtgraph UI failures observed on preceding head `c2c20c5`;
- the exact three failing nodes also fail identically on implementation base
  `main@6a0a334d61a7495b9c3433edfcbd537c8df59468` under the same Windows offscreen
  environment (`3 failed in 8.72s`), proving they are not introduced by P5-F;
- the three failures remain explicit pre-existing/offscreen validation debt rather
  than a claimed full-suite PASS.

Not observed:

- no real external GPU server was available;
- no production SMB share was available for timing characterization;
- no real server build/algorithm compatibility PASS is claimed;
- no wall-clock performance number is recorded as a correctness threshold.

No GitHub Actions or new CI workflow is introduced by P5-F.

## 2. Structural findings and retained corrections

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

The existing P5-C job-operation controller keeps its own separate max-two pool. Local
Statistics/Difference keeps the original analysis pool.

P5-F does not create a new Result parser, explorer, source registry, source loader,
residency manager, or numerical authority. Existing generation/stale-result rejection
continues to apply.

**Structural evidence**

Focused regressions now verify both levels:

- saturating the Remote IQA result/file pool does not prevent an unrelated local
  analysis worker from running;
- production composition directly binds P5-B/P5-D/P5-E to the Remote IQA pool while
  P5-C job operations and local analysis remain separate.

### 2.2 HTTP client lifetime and queued work

**Observed architecture before P5-F**

The P5-C helper functions correctly close their supplied client after each operation,
but the production factory supplied a newly constructed `HttpIqaJobClient` every time.
The underlying `httpx.Client` connection pool therefore could not survive across job
lifecycle requests.

The initial P5-F pool improved reuse but eagerly checked out the physical client from
`client_factory(...)`. P5-C calls that factory before queuing status/result/cancel
workers, so more clients could exist than physical worker slots and a cleared queued
worker could retain an unreleased lease.

**Review correction — lazy physical checkout**

`ReusableIqaClientPool.client()` now returns a cheap resource-free proxy:

- constructing a proxy creates no `HttpIqaJobClient` and does not increment active
  leases;
- physical client checkout occurs only on the proxy's first HTTP operation, which runs
  inside the worker;
- a queued worker cleared before `run()` therefore never creates or leases a physical
  client;
- closing an unused proxy is a no-op;
- an acquired client is never concurrently shared between worker threads;
- at most two idle endpoint clients are retained;
- returning an acquired proxy may reuse the underlying `httpx.Client`/keep-alive pool;
- pool/window close closes idle clients but never cancels a durable remote job;
- a client already executing is not closed underneath its worker and closes when the
  worker's helper returns it after pool shutdown.

No CREATE retry, polling cadence, result-reference recovery, publication semantics, or
server-owned cancel state semantics change.

**Structural evidence**

Unit regressions cover lazy proxy construction, unused close, idle reuse, concurrent
exclusive acquisition, idle retention bounds, and shutdown before/after acquisition.
A production-level regression queues four P5-C status operations into the max-two job
pool, blocks the first two, and verifies:

- exactly two physical clients are created while two more operations remain queued;
- only two active physical leases exist;
- shutdown clears queued work without creating clients for it;
- the two executing clients return/close after release;
- final active physical lease count is zero.

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

CREATE is called exactly once and status calls are serial. Optional cancel is issued at
most once. A legitimate non-terminal cancel response remains server-owned state and the
probe continues serial polling until a real terminal state or the actual status-request
bound. If `GET /result` fails after `succeeded`/`partial` was already observed, the trace
preserves that terminal state while reporting the Result-reference error separately.
The probe also mirrors the P5-C cross-state publication contract: `succeeded` requires
`complete`, while `partial` requires `partial`. A contradictory pair is reported as a
bounded protocol error while retaining the observed terminal and Result metadata.

The trace excludes the server URL, request body, credentials, source content, and
detailed transport exception text.

Developer entry point:

```powershell
.\.venv\Scripts\python.exe scripts\p5f_iqa_probe.py `
    <server-base-url> <request.json>
```

This command is prepared for later P5-G live-server use; no live-server PASS is claimed
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

Real mapped-share timing belongs to P5-G owner observation, not a repository correctness
threshold.

## 5. Diagnostics

P5-F extends the existing immutable **Help > Copy Diagnostics** snapshot rather than
creating a second diagnostics UI/framework.

The optional Remote IQA section contains bounded counters only:

- active/max Remote IQA result/file worker count;
- HTTP clients created;
- HTTP leases reused;
- active/max-active physical leases;
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

- Remote IQA Result/Reference/Inspect/history executor: fixed max 2 threads;
- P5-C job-operation executor: existing fixed max 2 threads, unchanged;
- reusable HTTP transport: no physical client for merely queued lazy proxies; max 2
  idle clients retained;
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

Focused P5-F files now include:

```text
tests/unit/test_p5f_transport_pool.py
tests/unit/test_p5f_compatibility_probe.py
tests/unit/test_p5f_diagnostics.py
tests/ui/test_p5f_worker_isolation.py
```

Owner-local evidence on implementation head
`f9a81b008d660405fc01e775607d78a91676093e`:

```text
focused P5-F pytest        PASS (26 passed in 1.69s)
scripts/check_docs.py      PASS
full pytest -q             925 passed, 1 skipped, 3 failed in 292.41s
ruff check .               PASS
ruff format --check .      PASS (261 files already formatted)
mypy src                   PASS (120 source files)
pip check                  PASS
git diff --check           PASS
```

The full-suite failures are
`test_floating_plots_geometry_survives_hide_show_and_restart`,
`test_single_view_plots_cover_all_selected_images_with_legends_and_tooltips`, and
`test_bayer_statistics_profiles_status_and_channel_split`. A temporary archive of base
`main@6a0a334d61a7495b9c3433edfcbd537c8df59468` was imported directly from its own
`src` tree and those exact nodes reproduced the same failures (`3 failed in 8.72s`) in
the same Windows offscreen environment. They are therefore carried as explicit
pre-existing/offscreen validation debt, not a P5-F regression and not a full-suite
PASS. The skipped symlink-escape case requires a Windows privilege unavailable in this
environment. P5-F does not add or require GitHub Actions for this purpose.

## 10. P5-G deferred owner real GPU / SMB matrix

When the environment becomes available, P5-G records observations for:

- Current Pair submit → COMPLETE → Open Result → Reference → Inspect/spatial;
- Folder Pair with representative Scene counts and deterministic order/progress;
- PARTIAL successful/failed-or-cancelled Scene mix;
- early and late cancel/publication race;
- Recent historical reopen and root remap;
- shared-root source, staged source, staging dedupe, mapped Result open;
- concurrent local Statistics/Difference/Display Gain/ROI/Line/page navigation;
- close/reopen and rapid Result/Scene changes.

Record client head SHA, server build/algorithm identifiers when available, approximate
Scene/source count, storage topology, and observed timings. Do not convert those timing
observations into correctness thresholds unless a concrete regression is later frozen.

## 11. P5-F merge and P5 closure

P5-F remains Active while PR #45 is unmerged. After exact-head owner revalidation,
independent latest-head review, and owner approval, P5-F may merge and be marked
**P5-F Complete**.

That merge does **not** mark the overall P5 program Complete. The active P5 plan then
moves to **P5-G — External GPU/SMB Validation & Closeout**, pending real environment
access.

Only after P5-G observes the real external gate may the repository:

1. record final P5-G evidence/identity;
2. mark P5 Remote IQA Platform Complete;
3. archive the active P5 plan under `docs/exec-plans/completed/`;
4. make P6 **Identity, Access & Remote Operations** the active/next program.

P6/P7 implementation is outside this branch.
