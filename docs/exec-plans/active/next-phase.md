# Execution plan: P5 — Remote IQA Platform

Status: Active — **P5-D Viewer-linked Scene Inspection / narrow reviewer closeout**
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
debug-harness authority. Its PR closeout validation is historical and is not carried
forward as a P5-D PASS.

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

Optional `storage_root_id` is additive source-location metadata. It is excluded from
immutable source equality and `measurement_context_id`; old v2 artifacts without it
remain readable but cannot enter native Inspect by guessing a local root.

Schema v1 remains explicit read-only compatibility.

## P5-D — active scope

### D1 — portable native-source lookup and explicit Inspect

Implemented contract:

- Results browsing is passive until **Inspect in Viewer**;
- P4-A temporary Picks block initial Inspect;
- source binding may add optional `storage_root_id` without schema bump;
- omission remains valid old-v2 read compatibility but cannot native-Inspect;
- locator is location metadata and excluded from source equality and
  `measurement_context_id`;
- P5-C logical root/containment/path validation remains authority;
- P5-D reuses the exact P5-C ordinary-image header probe/format acceptance;
- every unique native source is decoded from one encoded byte buffer and SHA-256 over
  that same buffer must match the published source;
- the exact decoded `ImageDocument` carrying that verified SHA is the generation
  committed to local Files/viewer authority;
- all Scene bindings must verify before registration/selection mutation;
- repeated variant bindings to the same `source_id` collapse onto one canonical native
  Files source while retaining all IQA variant aliases;
- distinct source identities may not claim one physical locator;
- >6 variant bindings are rejected without silent truncation;
- canonical registration reuses already-Registered source paths;
- before presentation, canonical load tokens are advanced and every verified decoded
  generation is published/accounted under its canonical document ID;
- only after all exact verified generations are present does canonical Selected/render
  run, so viewer/Statistics/Difference cannot observe an older resident generation;
- Selected/Current Comparison Page protection is active before the following eviction
  enforcement;
- replacing stale resident or evicted bytes keeps document identity but advances source
  generation and invalidates dependent source-view caches.

### D2 — Return and curation lifecycle

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
not an invalidation trigger. A temporary Pick created after Inspect is newer curation
intent: P5-D preserves the Pick and invalidates/disables Return rather than clearing
that Pick to restore an older workspace snapshot.

### D3 — Reference, Primary, and shared-source spatial binding

IQA `Reference` and local viewer `Primary` are separate identities. Neither control may
rewrite the other.

Repeated variant bindings may share one concrete native source. Result identities stay
N-way even though the native Files/viewer layer intentionally keeps one concrete source
document for that `source_id`.

For a shared native source, P5-D provides a bounded **Shared-source spatial binding**
selector. Every aliased `variant_id` remains reachable without duplicating Files
identity. The selected alias becomes the target consumed by overlay painting and Block
Inspector for that document. Reference selection remains independent.

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

Scene verification and spatial loading use feature-local workers.

A source verification callback publishes only when all relevant identity still matches:

- controller generation;
- result identity;
- selected Scene;
- local-intent generation;
- Remote IQA logical-root settings revision.

A spatial callback additionally requires its current Scene/attribute/Reference/mode
request identity. New IQA Result open and shutdown cancel feature-local work and clear
overlay state. Live root-mapping changes increment the P5-D locator revision, cancel
pending verification started under older mappings, and refresh Inspect availability.
Stale callbacks do not mutate the workspace.

### D6 — deterministic fixtures/regressions

Implemented/required fixture cases include:

- valid native sources;
- missing/hash/dimension source failures;
- exact encoded-buffer SHA to decoded-generation identity;
- already-Registered stale-resident replacement;
- P5-C/P5-D BMP/JPEG probe parity;
- repeated `source_id` variant aliases and conflicting physical-locator rejection;
- shared-source alias selection driving overlay and Block Inspector while Files remains
  one canonical document;
- post-Inspect Pick/Return preservation;
- root-remap pending-worker stale drop and availability refresh;
- missing/corrupt Scene grid;
- non-integer affine;
- non-zero grid origin;
- discarded borders;
- multiple attributes;
- invalid/pair-invalid cells.

## P5-D current validation status

Owner validation passed on prior closeout head `164ac2bd7f1a1870ea8eeb284821ad33a8ca275c`
for Ruff lint/format, mypy, and the then-current focused P5-D regression set; the
immediately preceding head also recorded `883 passed` for the full repository suite.

The independent re-review at `164ac2b...` closed five of six substantive prior
findings and requested one narrow alias-presentation fix plus documentation/test-path
corrections. Those changes move the branch head again, so **no exact-head PASS is
claimed for the new closeout head until the owner reruns the corrected gate**.

## P5-D execution order

### Step 1 — source/geometry/numerical implementation — Implemented

- additive locator parse/domain;
- logical-root resolution and all-or-nothing verification;
- exact decoded-source identity binding;
- per-cell spatial derivation;
- geometry hit-test;
- vector overlay/block inspector.

### Step 2 — viewer/workspace lifecycle — Implemented / reviewer closeout applied

- explicit Inspect;
- pre-Inspect Pick guard;
- canonical registration/selection;
- exact verified decode commit before presentation;
- stale resident replacement under canonical document identity;
- repeated-source variant alias collapse with active spatial alias selector;
- first Return snapshot;
- linked Scene replacement;
- newer-local-intent and post-Inspect Pick invalidation;
- live root-mapping revision stale-drop;
- stale-result/new-result/shutdown boundaries;
- Single/Multi viewer Return restoration.

### Step 3 — focused regression closeout — Active

Required focused files:

```text
tests/unit/test_p5d_scene_inspection.py
tests/unit/test_p5d_source_locator_identity.py
tests/unit/test_p5d_review_closeout_unit.py
tests/ui/test_p5d_viewer_linked_inspection.py
tests/ui/test_p5d_stale_inspection.py
tests/ui/test_p5d_review_closeout.py
tests/ui/test_p5d_alias_spatial_binding.py
```

Review them specifically for:

- old-v2 compatibility and locator fingerprint independence;
- all-or-nothing local authority;
- exact encoded SHA-to-decoded-generation binding;
- stale resident replacement and source generation/cache invalidation;
- P5-C/P5-D header-probe parity;
- repeated-source aliases without duplicate native Files identity;
- alias switching reaching each variant field in overlay and Block Inspector;
- Single View page + actual Active restoration;
- pre/post P4-A Pick behavior;
- root-remap stale callbacks and live availability;
- Reference/Primary independence;
- stale Scene/result callback/close safety;
- no source-resolution overlay allocation.

### Step 4 — durable-doc reconciliation — Active

Reconcile P5-C as merged and P5-D as active across schema-v2 authority,
P5-D contract, Product Spec, User Guide, Roadmap, Current State, and this execution
plan. Historical `REMOTE_IQA_V1_SPEC.md` remains unchanged.

### Step 5 — focused owner validation

Run on Windows against the exact P5-D PR head:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\unit\test_p5d_scene_inspection.py `
    tests\unit\test_p5d_source_locator_identity.py `
    tests\unit\test_p5d_review_closeout_unit.py `
    tests\ui\test_p5d_viewer_linked_inspection.py `
    tests\ui\test_p5d_stale_inspection.py `
    tests\ui\test_p5d_review_closeout.py `
    tests\ui\test_p5d_alias_spatial_binding.py `
    -q

.\.venv\Scripts\python.exe -m ruff check `
    src\pixelscope\core\image_document.py `
    src\pixelscope\io\image_reader.py `
    src\pixelscope\remote\iqa_scene_inspection.py `
    src\pixelscope\remote\iqa_spatial.py `
    src\pixelscope\remote\iqa_geometry.py `
    src\pixelscope\ui\iqa_scene_inspection.py `
    src\pixelscope\ui\iqa_scene_inspection_lifecycle.py `
    tests\unit\test_p5d_scene_inspection.py `
    tests\unit\test_p5d_source_locator_identity.py `
    tests\unit\test_p5d_review_closeout_unit.py `
    tests\ui\test_p5d_viewer_linked_inspection.py `
    tests\ui\test_p5d_stale_inspection.py `
    tests\ui\test_p5d_review_closeout.py `
    tests\ui\test_p5d_alias_spatial_binding.py

.\.venv\Scripts\python.exe -m ruff format --check `
    src\pixelscope\core\image_document.py `
    src\pixelscope\io\image_reader.py `
    src\pixelscope\remote\iqa_scene_inspection.py `
    src\pixelscope\remote\iqa_spatial.py `
    src\pixelscope\remote\iqa_geometry.py `
    src\pixelscope\ui\iqa_scene_inspection.py `
    src\pixelscope\ui\iqa_scene_inspection_lifecycle.py `
    tests\unit\test_p5d_scene_inspection.py `
    tests\unit\test_p5d_source_locator_identity.py `
    tests\unit\test_p5d_review_closeout_unit.py `
    tests\ui\test_p5d_viewer_linked_inspection.py `
    tests\ui\test_p5d_stale_inspection.py `
    tests\ui\test_p5d_review_closeout.py `
    tests\ui\test_p5d_alias_spatial_binding.py

.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

### Step 6 — owner manual validation

Follow the checklist in `docs/P5D_VIEWER_INSPECTION.md`, including:

- valid/missing/hash-mismatch source mappings;
- P5-C/P5-D source-format/header parity;
- already-Registered resident bytes replaced by verified result bytes;
- 2–6 variant-binding Inspect and >6 non-truncation;
- repeated `source_id` aliases using one native Files source, with A/B spatial binding
  switching reflected in overlay and Block Inspector;
- linked Scene navigation retaining first Return target;
- Single/Multi Return for Selected >6;
- newer local intent invalidation;
- post-Inspect Pick preservation and Return invalidation;
- live logical-root remap during verification;
- Reference/Primary independence;
- known spatial geometry and invalid cells;
- Difference/Display Gain/ROI/Line/zoom/pan/sync interactions;
- rapid Scene/attribute/Reference changes;
- new Result open and close/recreate during work.

### Step 7 — independent whole-PR re-review

Reviewer inspects the latest head only, including the previously requested P1/P2
closeout items. Any merge blocker returns to implementation → focused validation →
fresh review.

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
