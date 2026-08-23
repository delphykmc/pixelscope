# Execution plan: P5 — Remote IQA Platform

Status: Active — **P5-E Historical Result Workflow / Draft PR #44**
Owner: repository owner + P5 orchestrator + slice implementation/review agents
Last updated: 2026-08-23
Current merged main: `b086443d188eb9daae4bbf4f0faab3ff1d114f93`

Authoritative P5 documents:

- product/transport/ownership contract:
  [`docs/REMOTE_IQA_CONTRACT.md`](../../REMOTE_IQA_CONTRACT.md)
- current numerical/result contract:
  [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)
- completed P5-D viewer-linked inspection contract:
  [`docs/P5D_VIEWER_INSPECTION.md`](../../P5D_VIEWER_INSPECTION.md)
- active P5-E historical-result contract:
  [`docs/P5E_HISTORICAL_RESULTS.md`](../../P5E_HISTORICAL_RESULTS.md)
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

Observed evidence and planned validation remain separate. A PASS from P5-C/P5-D or an
older P5-E head is not validation of the latest P5-E head.

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

P5-E must not create another authority for Files/Selected/Current Comparison Page,
source residency/protection/preload, Difference/cache, Display Gain, native analysis,
or Session v1.

The canonical Result path remains P5-B with P5-A2/v1 reader dispatch. P5-D remains the
only explicit native source verification/Inspect bridge.

## Completed P5 baseline

| Slice | Status | Authority |
|---|---|---|
| P5-0 | Complete — PR #36 | program setup/contracts |
| P5-A | Complete — PR #37 | historical executable schema v1 |
| P5-A2 Stage 1 | Complete — PR #39 | durable schema-v2 model |
| P5-A2 Stage 2 | Complete — PR #40 | executable schema-v2 reader/math/artifacts |
| P5-B | Complete — PR #38 | canonical local IQA Results workspace |
| P5-C | Complete — PR #42 | submission/shared storage/jobs/PARTIAL |
| P5-D | **Complete — PR #43** | verified viewer-linked Scene Inspect/Return |

P5-B merged at `a44978db783ebcecb0d55f8abb52b583e0fdc47c`.
P5-D merged as current
`main@b086443d188eb9daae4bbf4f0faab3ff1d114f93`.

## Current executable schema-v2 contract

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 separates stable `variant_id`, concrete `source_id`, evaluation `scene_id`,
and `measurement_context_id`. Server-authored W/S1/S2/count/valid remain measurement
authority. PixelScope derives pair-valid comparisons with canonical helpers.

Optional `storage_root_id` is source-location metadata only and is excluded from
immutable source equality and measurement-context identity. Schema v1 remains explicit
read-only compatibility.

## P5-E scope

### E1 — Historical Result Locator

Implement Qt-free typed locator models:

```text
LogicalIqaResultLocator(storage_root_id, relative_path)
LocalIqaResultLocator(absolute_path)
```

Rules:

- logical locator is the portable production form;
- current machine mapping resolves only at reopen time;
- P5-C `resolve_result_reference()` remains the containment/availability authority;
- Jobs retain the server-published logical Result locator;
- a successful manual schema-v2 open may become logical history only when the proposed
  most-specific logical locator resolves through P5-C to the same canonical opened
  Result directory;
- lexical root membership alone must not manufacture a portable locator for a
  symlink/junction escape or otherwise unreproducible path;
- manual/out-of-root, unreproducible v2, and v1 Results may retain a local absolute
  locator;
- mapped drive/UNC path is never stored as the portable logical identity.

### E2 — Recent IQA Results

Add separate bounded observer persistence:

```text
key = recent/iqa_results
payload_version = 1
limit = 10
ordering = MRU
dedup = locator identity
```

Required behavior:

- malformed/future individual records are skipped;
- oversized/malformed containers do not become application authority;
- successful File, Jobs, and Recent opens record;
- failed/unsupported/corrupt/identity-mismatch opens do not record;
- Recent reopen moves the same locator to MRU;
- missing/offline/remapped entries remain until explicit Remove/Clear;
- P4-C Recent Images/Folders/Sessions remain unchanged;
- ApplicationSettings schema remains v6.

### E3 — Historical identity and Result-only mode

A successful open records observed:

```text
result_id + schema_version
```

Recent reopen validates that identity after the canonical reader succeeds but before
Results presentation changes. Mismatch keeps the prior valid Result and the existing
history entry.

No new whole-result digest is introduced.

Result open remains summary-first and does not stat/hash/decode every native source.
Missing/offline/unmapped source files do not make a structurally valid server Result
corrupt. Native source verification remains explicit P5-D Inspect authority.

### E4 — Provenance and historical compatibility

Add one passive Provenance page inside the existing Results workspace.

Schema v2 displays published:

- Result ID/schema/publication state;
- selected Scene measurement-context provenance;
- source IDs;
- optional logical storage root;
- relative path;
- SHA-256;
- dimensions;
- current local native-inspection status.

The existing P5-C/P5-D live `settings_changed()` chain remains authoritative for
machine-local root mappings. P5-E observes the completed chain and refreshes Provenance
immediately after root add/remove/remap without Result reopen or Scene reselection.

PARTIAL remains PARTIAL and existing failed/cancelled Scene diagnostics remain intact.

Schema v1 is explicitly historical/read-only. P5-E must not synthesize v2 root,
measurement-context, N-way, or absolute-source metadata.

### E5 — stale work / lifecycle / integration

- install P5-E after P5-D so every new Result open consumes P5-D teardown;
- use a P5-E resolver generation for the asynchronous logical-Recent stage that occurs
  before the canonical P5-B loader;
- any newer File/Jobs/Recent Result-open intent invalidates feature-local logical
  resolution before it can later start a canonical open;
- cancellation alone is insufficient; stale resolver callbacks must fail the P5-E
  generation guard even if their worker completes later;
- after resolution, rely on P5-B Result generation for canonical A→B stale callback
  rejection;
- keep one pending P5-E context for the latest Result generation;
- logical Recent resolution captures current P5-C mapping revision;
- remap during resolution/open cannot publish a path resolved under the old mapping;
- close invalidates/cancels feature-local locator resolution and clears pending context;
- close never cancels durable remote jobs;
- Session v1 remains unchanged and carries no IQA reference/state.

## Implementation status on Draft PR #44

Implemented on the branch:

- ROADMAP transition P5-D Complete / P5-E Active / P5-F Planned;
- P5-F1..P5-F5 planning split;
- typed locator/result-identity/Recent domain;
- independent `recent/iqa_results` repository;
- canonical File/Jobs/Recent open coordinator;
- pre-presentation historical identity gate;
- logical-root revision gate;
- passive Results Provenance page;
- explicit v1 historical/read-only presentation;
- P5-E resolver-generation lifecycle hardening across pre-loader Recent resolution and
  newer File/Jobs/Recent opens;
- live Provenance refresh after the existing P5-C/P5-D settings-change chain;
- authoritative same-directory validation before manual v2 logical-history promotion;
- focused lifecycle/canonicalization review regressions;
- unrelated top-level durable documentation restored to the merged-main content rather
  than condensed inside this feature PR;
- focused P5-E contract document.

Still required before P5-E Complete:

- exact-head automated/static validation after review fixes;
- owner Windows manual A–G validation;
- independent latest-head whole-PR re-review;
- owner merge approval.

## Focused automated validation

Run on the exact PR head:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\unit\test_p5e_iqa_history.py `
    tests\ui\test_p5e_historical_results.py `
    tests\ui\test_p5e_review_regressions.py `
    tests\ui\test_p5b_iqa_workspace.py `
    tests\ui\test_p5c_remote_iqa.py `
    tests\ui\test_p5c_result_mapping.py `
    tests\ui\test_p5c_debug_replay_ui.py `
    tests\ui\test_p5d_viewer_linked_inspection.py `
    tests\ui\test_p5d_stale_inspection.py `
    tests\ui\test_p5d_review_closeout.py `
    -q

.\.venv\Scripts\python.exe -m ruff check `
    src\pixelscope\app\application.py `
    src\pixelscope\app\iqa_history.py `
    src\pixelscope\remote\iqa_history.py `
    src\pixelscope\ui\iqa_historical_results.py `
    src\pixelscope\ui\iqa_historical_results_lifecycle.py `
    tests\unit\test_p5e_iqa_history.py `
    tests\ui\test_p5e_historical_results.py `
    tests\ui\test_p5e_review_regressions.py

.\.venv\Scripts\python.exe -m ruff format --check `
    src\pixelscope\app\application.py `
    src\pixelscope\app\iqa_history.py `
    src\pixelscope\remote\iqa_history.py `
    src\pixelscope\ui\iqa_historical_results.py `
    src\pixelscope\ui\iqa_historical_results_lifecycle.py `
    tests\unit\test_p5e_iqa_history.py `
    tests\ui\test_p5e_historical_results.py `
    tests\ui\test_p5e_review_regressions.py

.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest tests\unit\test_docs_contract.py -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

After focused validation, run the repository-standard full suite before merge.

Owner Windows automated/static validation was reported PASS on pre-review Draft head
`dd1ebfb8aa4846233de854fcd3cb313f069161e9`. Independent review then moved the branch
through additional fixes, so that PASS is historical evidence only. No PASS is recorded
for the post-review exact head until the commands above and the full suite are observed.

## Owner manual validation

Use the A–G checklist in
[`docs/P5E_HISTORICAL_RESULTS.md`](../../P5E_HISTORICAL_RESULTS.md):

A. Recent / MRU / Clear
B. logical-root remap + live Provenance mapping refresh
C. offline / missing / replacement identity
D. Result-only / native source failure
E. Provenance / schema v1 / PARTIAL
F. lifecycle / P5-D teardown / delayed logical Recent → newer File/Jobs / rapid canonical
   A→B / close-recreate
G. local-workspace authority

Record exact-head observations in PR #44.

## Independent review gate

After implementation, tests, docs, and owner manual validation are updated:

1. re-open exact PR #44 state;
2. confirm base is still the intended latest `main` or rebase deliberately if main moved;
3. review the whole PR, not only the newest commit;
4. inspect P5-B/P5-C/P5-D compatibility and Session/P4 Recent boundaries;
5. resolve all merge-blocking review findings;
6. rerun affected validation after any correction;
7. keep the PR Draft until all merge gates are complete.

## P5-F handoff — Planned

P5-E does not implement P5-F. The next slice is explicitly split into:

### P5-F1 — Real GPU Server Compatibility

- validate actual external GPU API/result writer compatibility;
- reconcile protocol edge cases without changing frozen Result/source identities ad hoc.

### P5-F2 — SMB / Network / Grid Performance Characterization

- characterize shared-storage filesystem calls, bandwidth, latency, and failure behavior;
- measure Result open, Reference preparation, historical reopen, and native Inspect.

### P5-F3 — Cache / HTTP / Retry / Backoff Tuning

- tune HTTP session reuse, polling/backoff, and result-reference retry from measurements;
- add bounded grid cache/preload only if measurements justify it.

### P5-F4 — Stress / Failure / Lifecycle Hardening

- large jobs/batches and COMPLETE/PARTIAL/failure/cancel cases;
- disconnect/reconnect, stale callbacks, rapid reopen/Inspect, close/recreate;
- prove remote batch membership never becomes local source/residency authority.

### P5-F5 — Optional Detail Characterization + P5 Closure

- characterize optional detail artifacts and decide whether typed detail support is
  justified;
- close P5 documentation and archive this execution plan only after P5-F is complete.
