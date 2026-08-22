# Execution plan: P5 — Remote IQA Platform

Status: Active — **P5-D Viewer-linked Scene Inspection / implementation and review**
Owner: repository owner + P5 orchestrator + slice implementation/review agents
Last updated: 2026-08-23
Current merged main: `24b328d02c0cd56fb79920e069af06d6e4cb706f`

Authoritative P5 documents:

- product/transport/ownership contract:
  [`docs/REMOTE_IQA_CONTRACT.md`](../../REMOTE_IQA_CONTRACT.md)
- current numerical/result contract:
  [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)
- P5-D viewer-linked inspection specialization:
  [`docs/P5D_VIEWER_INSPECTION.md`](../../P5D_VIEWER_INSPECTION.md)
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

Observed evidence and planned validation remain separate. A PASS from P5-C or an older
P5-D head is not validation of the latest P5-D head.

## Goal

P5 connects PixelScope to an external GPU IQA service while preserving PixelScope as a
fast local comparison tool.

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
explicit Inspect in Viewer
    ↓
verified native Scene sources + spatial grid inspection
    ↓
explicit Return to prior local comparison
```

The external GPU model/server lives outside this repository. PixelScope owns client
preparation, transport contract, portable storage identity, stable result parsing,
local reference-dependent exploration, and viewer-linked inspection.

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

P5-D must not create another authority for Files/Selected/Current Comparison Page,
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
| P5-C | **Complete — PR #42** | submission/shared storage/jobs/PARTIAL |

P5-B merged at `a44978db783ebcecb0d55f8abb52b583e0fdc47c` and remains the
canonical Open IQA Result / Results UI authority.

P5-C merged as `main@24b328d02c0cd56fb79920e069af06d6e4cb706f` and remains the
canonical Remote IQA settings, shared-storage, staging, job transport, PARTIAL, and
debug-harness authority. Its PR closeout records independent review PASS and owner
final full validation PASS; that evidence is historical and not carried forward as a
P5-D PASS.

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
pair-valid comparisons and uses canonical v2 helpers rather than UI-local math.

Schema v1 remains explicit read-only compatibility.

## P5-D — active scope

### D1 — portable native-source lookup and explicit Inspect

Implemented contract:

- Results browsing is passive until **Inspect in Viewer**;
- P4-A temporary Picks block Inspect;
- source binding may add optional `storage_root_id` without schema bump;
- omission remains valid old-v2 read compatibility but cannot native-Inspect;
- locator is location metadata and excluded from `measurement_context_id`;
- P5-C logical root/containment/path validation remains authority;
- dimensions are bounded-header probed;
- SHA-256 from the existing source resolver is compared with the published source;
- all Scene sources must verify before registration/selection mutation;
- duplicate physical sources or >6 variants are rejected rather than silently
  collapsed/truncated;
- canonical registration reuses already-Registered source paths;
- successful verified source order is passed to the canonical Selected/current-page
  workflow.

### D2 — Return lifecycle

The first successful Inspect captures exactly one transient snapshot:

```text
Selected order
Comparison Page anchor
applicable Active
applicable Primary
layout mode
```

Linked Scene navigation keeps that first snapshot.

Return:

- restores Selected through canonical selection authority;
- explicitly commits the captured Comparison Page after selection reset;
- restores the actual Single View Active document or Multi View Active tile;
- restores applicable Primary in Multi View;
- does not persist the snapshot into Session v1.

Newer non-IQA Selected/Files/layout/Primary intent invalidates Return. Active alone is
not an invalidation trigger.

### D3 — Reference and Primary independence

IQA `Reference` and local viewer `Primary` are separate identities. Neither control may
rewrite the other.

### D4 — spatial grid derivation and overlay

P5-D uses existing lazy schema-v2 grid loading.

For one valid source cell:

```text
absolute = S1 / W
```

Relative power uses canonical raw target/reference dB with the attribute epsilon.
Relative signed uses raw target-reference delta. Pair-invalid cells remain invalid.
Quality-direction sign flipping is not applied to the raw spatial field.

Geometry is shared by draw and hit-test:

```text
analysis cell polygon --inverse affine--> source polygon --> ImageViewer ViewBox
source cursor --forward affine--> analysis point --> grid row/column
```

The same path handles non-zero origins, non-integer affine transforms, valid rectangles,
and discarded right/bottom borders.

Overlay is vector/block based. No source-resolution heatmap/alpha image is allocated.
Block Inspector exposes bounded W/S1/S2/count/valid/mean/reference/pair/geometry detail.

### D5 — async/stale safety

Scene verification and spatial loading use feature-local workers and publish only when
controller generation, result identity, Scene, and spatial request still match.

New IQA Result open and shutdown cancel feature-local work and clear overlay state.
Stale callbacks do not mutate the workspace.

### D6 — deterministic fixtures/regressions

Implemented/required fixture cases include:

- valid native sources;
- missing/hash/dimension source failures;
- missing/corrupt Scene grid;
- non-integer affine;
- non-zero grid origin;
- discarded borders;
- multiple attributes;
- invalid/pair-invalid cells.

Focused tests cover source-locator compatibility, numerical spatial derivation,
geometry/hit-test consistency, passive Results behavior, Pick guard, already-Registered
reuse, all-or-nothing failure, Return restore/invalidation, and Reference/Primary
independence.

## P5-D current validation status

No exact-head automated or owner Windows PASS has been observed yet in this execution
plan. The implementation branch must therefore remain review/validation pending.

The agent environment used for this implementation cannot clone the repository from
GitHub into its shell, so no local pytest/Ruff/mypy result is claimed here. Repository
validation must come from an actual CI run if configured or from the owner's Windows
`.venv`.

## P5-D execution order

### Step 1 — source/geometry/numerical implementation — Implemented

- additive locator parse/domain;
- logical-root resolution and all-or-nothing verification;
- per-cell spatial derivation;
- geometry hit-test;
- vector overlay/block inspector.

### Step 2 — viewer/workspace lifecycle — Implemented

- explicit Inspect;
- Pick guard;
- canonical registration/selection;
- first Return snapshot;
- linked Scene replacement;
- newer-local-intent invalidation;
- stale-result/new-result/shutdown boundaries;
- Single/Multi viewer Return restoration.

### Step 3 — focused regression closeout — Active

Required focused files:

```text
tests/unit/test_p5d_scene_inspection.py
tests/ui/test_p5d_viewer_linked_inspection.py
```

Review them specifically for:

- old-v2 compatibility;
- all-or-nothing local authority;
- ordering/reuse;
- Single View page + actual Active restoration;
- P4-A guard;
- Reference/Primary independence;
- stale callback/close safety;
- no source-resolution overlay allocation.

### Step 4 — durable-doc reconciliation — Active

Reconcile P5-C as merged and P5-D as active. Historical
`REMOTE_IQA_V1_SPEC.md` must remain unchanged.

### Step 5 — focused owner validation

Run on Windows against the exact P5-D PR head:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\unit\test_p5d_scene_inspection.py `
    tests\ui\test_p5d_viewer_linked_inspection.py `
    -q

.\.venv\Scripts\python.exe -m ruff check `
    src\pixelscope\remote\iqa_scene_inspection.py `
    src\pixelscope\remote\iqa_spatial.py `
    src\pixelscope\remote\iqa_geometry.py `
    src\pixelscope\ui\iqa_scene_inspection.py `
    tests\unit\test_p5d_scene_inspection.py `
    tests\ui\test_p5d_viewer_linked_inspection.py

.\.venv\Scripts\python.exe -m ruff format --check `
    src\pixelscope\remote\iqa_scene_inspection.py `
    src\pixelscope\remote\iqa_spatial.py `
    src\pixelscope\remote\iqa_geometry.py `
    src\pixelscope\ui\iqa_scene_inspection.py `
    tests\unit\test_p5d_scene_inspection.py `
    tests\ui\test_p5d_viewer_linked_inspection.py

.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\check_docs.py
git diff --check
```

### Step 6 — owner manual validation

Follow the checklist in `docs/P5D_VIEWER_INSPECTION.md`, including:

- valid/missing/hash-mismatch source mappings;
- 2–6 variant Inspect and >6 non-truncation;
- already-Registered source reuse and exact source order;
- linked Scene navigation retaining first Return target;
- Single/Multi Return for Selected >6;
- newer local intent invalidation;
- Reference/Primary independence;
- known spatial geometry and invalid cells;
- Difference/Display Gain/ROI/Line/zoom/pan/sync interactions;
- rapid Scene/attribute/Reference changes;
- new Result open and close/recreate during work.

### Step 7 — independent whole-PR review

Reviewer inspects the latest head only. Any merge blocker returns to implementation →
focused validation → fresh review.

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

Only after exact-head validation and independent latest-head PASS may P5-D be marked
Complete and merged with owner approval.

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
- realistic reference-switch and Inspect latency;
- optional detail artifact characterization;
- P5 closure documentation.

Authentication/SSO/tokens/permissions remain P6. Packaging/signing/updater remains P7.
