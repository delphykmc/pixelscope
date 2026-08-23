# Quality and validation

PixelScope quality gates are correctness/ownership/lifecycle gates first. Performance
measurements are evidence for tuning, not substitutes for correctness.

Only validation actually observed on a named exact head may be recorded as PASS.
Historical PASS evidence from an earlier phase/head is not automatically valid for a
later PR head.

## Repository-standard validation

The normal merge validation stack is:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Focused suites may be run first, but a feature that changes runtime code still requires
the repository-standard suite before merge unless the repository owner explicitly
records a narrower exception.

## General correctness invariants

The test suite must protect these durable invariants:

- native `ImageDocument.source` remains local analysis authority;
- presentation-only Display Gain never changes source generation or native analysis;
- Difference family/domain/math remains explicit and generation-aware;
- Registered/Selected/Current Comparison Page/Presented/Resident remain separate;
- `Analysis Working Set = Current Comparison Page`;
- large Selected/Pick sets do not become Selected-wide residency/preload owners;
- worker cancellation is advisory and stale results are rejected by identity/generation;
- close/recreate does not leave active callbacks able to mutate a new window;
- observer metadata failure never breaks authoritative runtime work.

## P2/P3/P4 regression coverage

Existing unit/UI/integration tests continue to cover:

- typed Settings migration/reset and future-schema safety;
- source residency accounting/protection/eviction;
- Folder Position preload/promotion and stale work;
- runtime diagnostics sanitization;
- Gray/RGB/Bayer Difference and mixed-depth normalized Difference;
- RAW Display Gain semantics and general Display Gain;
- unified input and large Current Comparison Pages;
- temporary Pick/Keep curation;
- Session v1/legacy Comparison Set compatibility;
- typed Recent Images/Folders/Sessions;
- focused export;
- P4 workflow integration/close-recreate.

P5-E must not weaken those regressions.

## Remote IQA numerical/result quality

`REMOTE_IQA_V2_SPEC.md` is the current numerical/artifact contract. Required tests cover:

- deterministic schema-v2 fixtures;
- manifest/summary/grid safety ceilings and path containment;
- W/S1/S2/count/valid recomposition;
- published summary consistency;
- exact geometry invariants;
- pair-valid comparison math;
- both power modes;
- signed delta;
- Dataset absolute/relative reductions;
- v1 explicit read-only dispatch;
- COMPLETE/PARTIAL structural rules and successful-Scene ordering.

No P5-E change may add a second numerical parser or alternate IQA math path.

## P5-B Results quality — Complete

P5-B regression coverage remains authoritative for:

- canonical File Result open;
- summary-first schema-v2 presentation;
- N-way Absolute/Reference switching;
- deferred one-Scene-at-a-time grid preparation;
- last-valid rollback after deferred failure;
- Scene Trend/hierarchy/source identity presentation;
- v1 historical read-only compatibility;
- IQA dock float/dock/maximize/reset;
- passive Results browsing not mutating local workspace authority.

## P5-C submission/storage quality — Complete

P5-C regression coverage remains authoritative for:

- schema-v6 Remote IQA settings;
- root-id/path validation and resolved containment;
- SHA-256 source identity;
- content-addressed staging and concurrent publication;
- deterministic Current Pair/Folder Pair request building;
- no RAW remote submission conversion;
- bounded Jobs polling/cancel/result-reference recovery;
- no blind create retry;
- COMPLETE/PARTIAL terminal/result-reference consistency;
- root-remap stale result-path rejection;
- Request Inspector/Replay/local HTTP contract harnesses;
- proof remote batch preparation does not become Files/Selected/current-page/
  source-residency/preload authority.

## P5-D viewer inspection quality — Complete

P5-D / PR #43 merged into
`main@b086443d188eb9daae4bbf4f0faab3ff1d114f93` after its own exact-head validation and
independent review.

P5-D regressions protect:

- passive browsing until explicit Inspect;
- all-or-nothing source verification;
- exact encoded-byte SHA identity;
- stale resident replacement with verified generation;
- repeated-source variant aliases using one canonical Files source;
- root-remap stale verification rejection;
- first-Inspect Return capture and newer-local-intent invalidation;
- Pick/Return interaction;
- vector spatial geometry and Block Inspector;
- source/residency/viewer authority reuse;
- new Result and close teardown.

That historical PASS does **not** validate P5-E changes automatically.

## P5-E Historical Result quality — Active / Draft PR #44

Focused contract:
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

### Unit-level requirements

`tests/unit/test_p5e_iqa_history.py` covers the Qt-free observer domain:

- logical/local locator round-trip;
- observed Result identity round-trip;
- malformed record rejection;
- future payload-version rejection;
- traversal-invalid logical locator rejection;
- max-10 bound;
- MRU ordering;
- locator-based deduplication;
- malformed records not deleting valid neighboring entries;
- most-specific manual-v2 root canonicalization;
- v1 local-locator fallback;
- Clear remaining independent from ApplicationSettings keys.

### UI/integration requirements

`tests/ui/test_p5e_historical_results.py` covers the production composition:

- successful canonical manual Result open records Recent;
- valid Result remains browseable without native source files;
- Provenance exposes published v2 identity/context/source hash metadata;
- Recent identity mismatch preserves the exact last-valid Result object and history;
- Jobs open preserves server-published logical locator instead of mapped local path;
- schema-v1 history remains local and explicit historical/read-only;
- schema-v1 Provenance does not synthesize v2 measurement-context/root fields;
- PARTIAL history preserves publication state and failed Scene diagnostics;
- Recent IQA history persists across window close/recreate.

Existing P5-B/P5-C/P5-D regressions are intentionally included in focused P5-E
validation because P5-E wraps those production paths rather than replacing them.

### Focused exact-head command

Run on the final P5-E PR head:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\unit\test_p5e_iqa_history.py `
    tests\ui\test_p5e_historical_results.py `
    tests\ui\test_p5b_iqa_workspace.py `
    tests\ui\test_p5c_remote_iqa.py `
    tests\ui\test_p5c_result_mapping.py `
    tests\ui\test_p5d_viewer_linked_inspection.py `
    tests\ui\test_p5d_stale_inspection.py `
    tests\ui\test_p5d_review_closeout.py `
    -q

.\.venv\Scripts\python.exe -m ruff check `
    src\pixelscope\app\application.py `
    src\pixelscope\app\iqa_history.py `
    src\pixelscope\remote\iqa_history.py `
    src\pixelscope\ui\iqa_historical_results.py `
    tests\unit\test_p5e_iqa_history.py `
    tests\ui\test_p5e_historical_results.py

.\.venv\Scripts\python.exe -m ruff format --check `
    src\pixelscope\app\application.py `
    src\pixelscope\app\iqa_history.py `
    src\pixelscope\remote\iqa_history.py `
    src\pixelscope\ui\iqa_historical_results.py `
    tests\unit\test_p5e_iqa_history.py `
    tests\ui\test_p5e_historical_results.py

.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest tests\unit\test_docs_contract.py -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

After focused validation, run the full repository-standard validation before merge.

### P5-E async/stale invariants

Automated/full regression plus manual validation must prove:

- rapid Result A→B cannot allow A's old callback to become current;
- one P5-E pending context corresponds to the latest P5-B Result generation;
- a logical Recent path resolved under an old root mapping cannot publish after remap;
- identity mismatch is rejected before Results `set_model()`;
- failure/mismatch does not create a newer history record;
- new Result open consumes P5-D inspection/spatial teardown;
- close cancels feature-local historical resolution and leaves no stale callback;
- durable remote jobs are not cancelled by PixelScope close.

### Result-only invariants

Opening/reopening a valid Result must not perform a dataset-wide native source hash/stat/
decode pass. Missing/offline/unmapped/changed native sources may make Inspect unavailable
or fail verification, but do not make the Result itself corrupt.

Provenance must remain metadata-only and must not load native pixels or compute IQA.

### Session and Recent isolation

P5-E validation must prove/confirm:

- `recent/iqa_results` is independent from P4 Recent Images/Folders/Sessions;
- Clear Recent IQA Results does not clear other Recent kinds;
- ApplicationSettings remains schema v6;
- Session v1 content/schema remains unchanged;
- no running job/Result locator/Reference/Scene/Provenance/Inspect/Return state is silently
  added to Session v1.

## P5-E owner Windows manual validation

Before merge, run the A–G checklist in
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md):

A. Recent / MRU / Clear
B. logical-root remap
C. offline / missing / replacement identity
D. Result-only / native source failure
E. Provenance / v1 / PARTIAL
F. lifecycle / P5-D teardown / rapid A→B / close-recreate
G. local-workspace authority

Record the exact tested head and observed results in PR #44.

## P5-E validation status at this document head

P5-E is **not Complete**.

The implementation environment used for Draft PR #44 cannot clone the repository into
its container over the network and, as of the last check, no GitHub Actions run/combined
status was available for the branch. Therefore this document does not claim focused,
full-suite, Ruff, mypy, docs, or pip-check PASS for the current head.

Required merge gates remain:

1. exact-head focused validation;
2. repository-standard full validation;
3. owner Windows manual A–G;
4. independent latest-head whole-PR review;
5. resolution of any findings with affected validation rerun;
6. owner merge approval.

## P5-F quality handoff — Planned

P5-F adds measured real-service/performance/stress evidence without redefining P5-E
correctness:

- real GPU server compatibility;
- SMB/network/grid performance characterization;
- measured cache/HTTP/retry/backoff tuning;
- batch/failure/disconnect/stale/close-recreate stress;
- optional detail-artifact characterization;
- final P5 closure validation/documentation.

No fixed wall-clock threshold is a correctness gate unless later explicitly approved and
documented from measured product requirements.
