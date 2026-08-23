# PixelScope current state

Snapshot date: 2026-08-23

Current merged `main`:
`b086443d188eb9daae4bbf4f0faab3ff1d114f93`

Active implementation branch:
`feature/p5-e-historical-iqa-results`

Active Draft PR:
**#44 — `[ChatGPT-assisted] Add historical Remote IQA result workflow`**

## Phase status

P5 **Remote IQA Platform** is Active in **P5-E — Historical Result Workflow**.

Merged P5 sequence:

- P5-0 / PR #36 — program setup;
- P5-A / PR #37 — historical executable schema-v1 compatibility;
- P5-A2 Stage 1 / PR #39 — durable schema-v2 contract;
- P5-A2 Stage 2 / PR #40 — executable schema-v2 reader/domain/math;
- P5-B / PR #38 — IQA Workspace & Local Result Exploration, merged at
  `a44978db783ebcecb0d55f8abb52b583e0fdc47c`;
- PR #41 — repository Ruff-format baseline;
- P5-C / PR #42 — Submission & Shared Storage;
- P5-D / PR #43 — Viewer-linked Scene Inspection, merged as current `main` at
  `b086443d188eb9daae4bbf4f0faab3ff1d114f93`.

P5-E is not merged and no P5-E validation PASS is implied by prior phase results.
P5-F remains Planned.

Active plan:
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

Durable P5 contract:
[`REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Current numerical/result contract:
[`REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).

Completed P5-D implementation contract:
[`P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md).

Active P5-E historical-result contract:
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

Historical schema-v1 compatibility contract:
[`REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).

## Authoritative local workspace model

PixelScope retains the P3/P4 ownership hierarchy:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset / page size 6
Current Comparison Page
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

- **Registered** is Files/catalog membership and is not limited to six.
- **Selected** is ordered logical comparison membership and may exceed six.
- **Current Comparison Page** is a derived bounded maximum-six working set.
- **Presented** is current viewer representation.
- **Resident** is decoded native source retained under P2 residency policy only while a
  correctness/runtime owner requires it.

`Analysis Working Set = Current Comparison Page`.

Remote IQA remains a parallel feature-local domain. Submission, Jobs, Results browsing,
historical reopen, and Provenance do not create another Files/Selected/source-residency
authority. P5-D changes Selected only after explicit **Inspect in Viewer**.

## Current local input policy

Supported local image families remain:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

Remote IQA submission remains intentionally narrower:

```text
.png  .bmp  .jpg  .jpeg
```

There is no silent RAW conversion for Remote IQA.

## Inherited runtime authorities

P5 does not redesign:

- exact decoded native `source.nbytes` residency accounting;
- independent source and Difference memory budgets;
- current-page/correctness source protection;
- off-page Selected/Picked sources remaining evictable;
- Folder Position `+1` speculative preload;
- RUNNING preload foreground promotion;
- application-owned bounded analysis/Display Gain workers;
- native `ImageDocument.source` authority for local Statistics, Histogram, Line Profile,
  Difference, and Split Channels;
- Display Gain as presentation-only state;
- explicit Difference Calculate as the only active-Difference establishment path;
- P4-A temporary Pick/Keep curation;
- Session v1;
- P4-C typed Recent Images/Folders/Sessions.

Remote IQA values are server-authored IQA measurements and are not native PixelScope
Statistics/Difference output.

## IQA result authority — executable schema v2

The governing rule remains:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 separates:

- `variant_id` — comparison configuration / IQA Reference slot;
- `source_id` — concrete source identity;
- `scene_id` — evaluation Scene;
- `measurement_context_id` — Scene measurement context.

Source bindings may include optional `storage_root_id` location metadata. It is excluded
from immutable source equality and from `measurement_context_id`.

Server measurement authority remains W/S1/S2/count/valid. Absolute and relative
reductions remain the P5-A2/P5-B canonical math. Schema v1 remains explicit read-only
historical compatibility with no synthetic v1→v2 upgrade.

## P5-B canonical Results workspace — Complete

P5-B owns the only result reader/controller/workspace path:

- **File > Open IQA Result...** version dispatch;
- summary-first schema-v2 Absolute default;
- N-way Reference switching;
- bounded deferred Scene-grid loading;
- canonical relative math;
- Overview and Scene Trend;
- COMPLETE/PARTIAL diagnostics;
- published source identity cards;
- Plots-equivalent dock/floating behavior;
- passive browsing that does not mutate local workspace authority.

P5-D and P5-E compose around this path rather than replacing it.

## P5-C submission and shared storage — Complete

Application settings schema v6 owns machine-local Remote IQA configuration:

```text
server_base_url
storage_roots[] {
    storage_root_id
    client_path
}
staging_root_id
```

Portable path identity is `storage_root_id + relative_path`; Windows/UNC client paths
are machine-local mappings.

P5-C owns:

- deterministic Current Pair and Folder Pair submission;
- SHA-256 source identity and content-addressed staging;
- path containment and publication hardening;
- non-modal Jobs polling/cancellation/result-reference recovery;
- logical Result reference resolution;
- COMPLETE/PARTIAL publication handling;
- Request Inspector / Replay JSON / localhost protocol test harnesses.

Only terminal `succeeded` and `partial` jobs may expose Results. Completion never
auto-opens a Result.

## P5-D viewer-linked Scene inspection — Complete

PR #43 is merged in current `main`.

P5-D provides the explicit bridge from an already-open schema-v2 Result to native local
inspection:

- Results remain passive until **Inspect in Viewer**;
- source root/location is resolved through P5-C authority;
- exact encoded bytes are SHA-256 verified before native commit;
- dimensions/decode/containment failures fail Inspect, not the server Result;
- all required Scene sources verify before local mutation;
- repeated variant aliases may share one canonical native source;
- verified generations publish into the ordinary Files/residency owner before Selected
  presentation;
- one transient Return snapshot is captured on first successful Inspect;
- newer local intent invalidates Return rather than being overwritten;
- schema-v2 grid geometry drives vector overlay and Block Inspector;
- result/Scene/local-intent/settings/spatial generations reject stale callbacks;
- new Result open and shutdown cancel/drop P5-D feature-local work.

See [`P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md) for the frozen contract.

## P5-E historical Result workflow — Active Draft

Draft PR #44 currently adds a historical-result layer **in front of** the existing P5-B
loader and **above** P5-D's new-result teardown.

### Typed historical locators

Two Qt-free locator forms are defined:

```text
LogicalIqaResultLocator
    storage_root_id
    relative_path

LocalIqaResultLocator
    absolute_path
```

Logical locators are the portable production form. Reopen resolves them through current
`RemoteIqaSettings` and P5-C `resolve_result_reference()` containment checks. Local
locators are machine-dependent fallback for manual/out-of-root and schema-v1 Results.

### Recent IQA Results

P5-E owns independent observer metadata:

```text
key: recent/iqa_results
payload version: 1
limit: 10
ordering: MRU
dedup: locator identity
```

It is intentionally outside `ApplicationSettings` schema v6 and does not modify P4-C
Recent Images/Folders/Sessions.

Only successful canonical Result opens record history. File, Jobs, and Recent paths all
converge on the P5-B loader. Jobs preserve the server-published logical locator rather
than the current mapped absolute path.

### Historical reopen identity

A successful open records observed:

```text
result_id + schema_version
```

Recent reopen checks this identity after canonical loading but before `set_model()`.
Mismatch therefore cannot replace the last valid currently presented Result and does not
silently rewrite the old history entry.

No new whole-result digest is introduced.

### Result-only behavior

Historical Result open does not stat/hash/decode all native sources. A valid Result stays
browsable when native source files are unavailable, unmapped, moved, or missing.

Native source verification remains lazy P5-D Inspect authority.

### Provenance

P5-E adds one passive **Provenance** page to the existing Results tab set. For schema v2
it exposes published Result identity/publication state, selected Scene
measurement-context provenance, source IDs, optional logical roots, relative paths,
SHA-256, dimensions, and current native-inspection status.

Schema v1 is explicitly labelled historical/read-only and receives no synthetic v2
metadata.

### Async/lifecycle

P5-E relies on the P5-B Result generation for rapid A→B stale-drop. Logical Recent
resolution also captures P5-C mapping revision. New Result open consumes the already
installed P5-D teardown path; P5-E does not bypass it. Close cancels only P5-E
feature-local locator resolution and never cancels durable remote jobs.

Focused contract and owner manual checklist:
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

## P5-E validation state

P5-E validation is **in progress** on Draft PR #44.

Added focused regression files currently include:

```text
tests/unit/test_p5e_iqa_history.py
tests/ui/test_p5e_historical_results.py
```

This environment has not observed a GitHub Actions run for the current PR head, and the
container cannot clone the private repository over the network. Therefore no local or CI
PASS is claimed here. Exact-head automated validation, owner Windows manual validation
A–G, and independent whole-PR latest-head review remain merge gates.

## Forward sequence

```text
P5-E Historical Result Workflow
    ↓
P5-F Integration & Performance Hardening
    ↓
P5 Complete
    ↓
P6 Identity, Access & Remote Operations
    ↓
P7 Release Engineering & Distribution
```
