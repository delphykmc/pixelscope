# PixelScope current state

Snapshot date: 2026-08-24
Current merged `main`: `7c3dbe386aaff900f0accc7ce460759df80f14e0`

`main` includes:

- P5-A / PR #37 — historical executable schema-v1 compatibility;
- P5-A2 Stage 1 / PR #39 — durable schema-v2 contract;
- P5-A2 Stage 2 / PR #40 — executable schema-v2 reader/domain/math;
- P5-B / PR #38 — IQA Workspace & Local Result Exploration, merged at
  `a44978db783ebcecb0d55f8abb52b583e0fdc47c`;
- PR #41 — repository Ruff-format baseline;
- P5-C / PR #42 — Submission & Shared Storage;
- P5-D / PR #43 — Viewer-linked Scene Inspection, merged at
  `b086443d188eb9daae4bbf4f0faab3ff1d114f93`;
- P5-E / PR #44 — Historical Result Workflow, merged at
  `6a0a334d61a7495b9c3433edfcbd537c8df59468`;
- P5-F / PR #45 — Integration & Performance Hardening, merged at
  `6634447fc3c48545a2482718dd3f444928806218`;
- R0 / PR #46 — state reconciliation and executable refactoring program, merged at
  `a25b3ee1b08dc26b57776fd2a24c3b751f13ebfc`;
- R1 / PR #47 — explicit application/Remote IQA composition seam, merged at
  `808f1e6bccd67e649be71b03798a1a1f407628f8`;
- R2 / PR #48 — explicit worker/resource ownership injection, merged at
  `7c0d326fd2a8ff767ac916d29af1c7d5ee44abd6`;
- R3-A / PR #49 — obsolete pre-P5 Remote scaffold disposition, merged at
  `a97bfb68e1113afea4ea905d7ccbbb1f67a9bde1`.
- R3-B / PR #50 — Session and legacy boundary clarification, merged at
  `6e98baea425f3dfbfacc1140370a77e889673a76`.
- R4-A / PR #51 — common UI test fixtures, merged at
  `336a27e5e10e3d5e8d83bc18046bec837daa5b96`.
- R4-B / PR #52 — smoke-suite decomposition, merged at
  `39b8c77fbf8a497d2787f33b8e119d2ddbed9604`.
- R5 / PR #53 — Windows/offscreen validation hardening, merged at
  `45e718abe28ab600edab41cf04a998029f6fc5f7`.
- R6 / PR #54 — harness and architecture guardrails, merged at
  `7c3dbe386aaff900f0accc7ce460759df80f14e0`.

P5 **Remote IQA Platform** is complete through P5-F. Overall P5 remains Active because
P5-G **External GPU/SMB Validation & Closeout** is unobserved and deferred until the
real environment is available. The current active repository program is **R —
Repository Refactoring & Validation Hardening**; it adds no product behavior.
R7 **Final Integration Validation and Closeout** is active on
`codex/r7-refactoring-closeout`.

Active plan:
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

Durable P5 product/transport contract:
[`REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Current numerical/result contract:
[`REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).

P5-D viewer-linked inspection contract:
[`P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md).

P5-E historical-result contract:
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

P5-F integration characterization:
[`P5F_INTEGRATION_CHARACTERIZATION.md`](P5F_INTEGRATION_CHARACTERIZATION.md).

Deferred P5-G external validation plan:
[`exec-plans/deferred/p5g-external-gpu-smb-validation.md`](exec-plans/deferred/p5g-external-gpu-smb-validation.md).

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
- **Resident** is decoded native source retained under P2 residency policy only while
  a correctness/runtime owner requires it.

`Analysis Working Set = Current Comparison Page`.

Viewer slots are page-local `1..6`; global Selected ordinal and viewer slot are
separate concepts.

Remote IQA remains a parallel feature-local job/result domain. Submission, Jobs,
historical Results, and passive result browsing do not create a second
Files/Selected/source-residency authority. P5-D may mutate Selected only at the explicit
**Inspect in Viewer** boundary, and then only through the canonical local
registration/selection workflow.

## Current local input policy

Supported local PixelScope image families remain:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

- **Open Images...** and direct-file drag/drop are selection-oriented.
- **Open Folder...** and folder drag/drop are registration-oriented.
- Folder registration does not replace Selected or presentation state.
- Registered-but-unselected is valid.
- unresolved folder RAW remains lazy until foreground intent requires profile
  resolution.

Remote IQA submission remains intentionally narrower:

```text
.png  .bmp  .jpg  .jpeg
```

There is no silent RAW conversion for Remote IQA.

## P2/P3/P4 authorities inherited by P5

P5 does not redesign:

- exact native `source.nbytes` decoded-source residency accounting;
- independent source and Difference memory budgets;
- current-page/correctness source protection;
- off-page Selected/Picked sources remaining evictable;
- Folder Position `+1` max-one speculative preload;
- RUNNING preload foreground promotion;
- application-owned bounded analysis/Display Gain workers;
- native `ImageDocument.source` authority for local Statistics, Histogram, Line
  Profile, Difference, and Split Channels;
- Display Gain as presentation-only state;
- explicit Difference Calculate as the only active-Difference establishment path;
- P4-A temporary Pick/Keep curation;
- Session v1 and typed Recent Images/Folders/Sessions.

Remote IQA values are server-authored IQA measurements and must not be presented as
native PixelScope Statistics/Difference output.

## Current IQA result authority — executable schema v2

The governing rule is:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 distinguishes:

- `variant_id` — comparison configuration / IQA Reference slot;
- `source_id` — one concrete source image;
- `scene_id` — evaluation Scene;
- `measurement_context_id` — Scene context that governs the published weighted
  measurement.

A source binding may additionally carry optional `storage_root_id` location metadata.
It is excluded from immutable source identity/equality and from
`measurement_context_id`; old schema-v2 artifacts that omit it remain result-readable.

For every published successful Scene, including successful Scenes inside PARTIAL:

- every declared variant is present exactly once in top-level variant order;
- multiple variant slots may intentionally reference the same concrete `source_id`;
- source dimensions and required physical geometry are compatible/exact as specified;
- PixelScope never aligns, resizes, imputes, or index-zips incompatible grids.

Server measurement authority remains W/S1/S2/count/valid. Canonical Scene absolute
mean is `ΣS1/ΣW`. Dataset absolute summaries expose pooled-weighted and equal-Scene
statistics; the default absolute Overview is `pooled_weighted_mean`.

Reference-dependent comparison is local and uses pair-valid support. The two power
modes remain ratio-of-weighted-means and mean-of-finite-grid-log-ratios. Signed
attributes retain signed target-minus-reference semantics. The default relative
Dataset Overview is the arithmetic mean of valid Scene comparison values.

Schema v1 remains explicit read-only historical compatibility and is never silently
upgraded to v2.

## P5-B canonical result workspace

P5-B / PR #38 owns the local result-browsing path:

- **File > Open IQA Result...** uses canonical version dispatch;
- schema v2 opens summary-first and defaults to Absolute;
- N-way `variant_id` Reference switching is supported;
- Reference-dependent preparation runs off the Qt thread and processes one Scene grid
  at a time while retaining derived scalar results rather than the full grid corpus;
- Absolute/Relative table and Scene Trend presentation reuse canonical v2 math;
- Scene cards expose published source identity/path/hash/location metadata;
- IQA Reference remains independent from local Primary;
- IQA dock float/dock/maximize/reset behavior follows the Plots workspace pattern;
- result browsing itself does not mutate local workspace authority.

P5-D composes explicit native Inspect on top of this workspace; it does not replace the
P5-B reader/controller. P5-E composes historical locator/identity/Provenance around the
same canonical open path.

## P5-C merged client workflow

P5-C / PR #42 is complete and owns Remote IQA Setup/Jobs/shared-storage transport.

### Settings ownership

Application settings schema v6 provides typed machine-local `RemoteIqaSettings`:

```text
server_base_url
storage_roots[] {
    storage_root_id
    client_path
}
staging_root_id
```

`storage_root_id + relative_path` is portable identity. Windows/UNC client paths are
machine-local configuration only. Server physical paths and credentials are not
stored in PixelScope request/result/session artifacts.

### Submission identity

Initial user-facing submission remains exactly two variants `A/B`.

Current Pair is the **A/B pair of underlying Current Comparison Page documents**.
Primary, Active, viewer reorder, Display Gain, Difference, and Split presentation do
not redefine submission identity.

Folder Pair uses immediate eligible non-symlink files, Unicode-NFC deterministic
lexical ordering, equal eligible counts, pair-by-index pairing, equal pair dimensions,
and at most 512 Scenes.

Requests serialize portable source identity/integrity metadata:

```text
storage_root_id
relative_path
sha256
width
height
```

Existing files under a configured root are referenced in place. Outside files may be
content-addressed into the selected staging root using SHA-256, guarded `.part`
publication, containment checks, and atomic final publication/reuse verification.

### Job API

```text
POST /v1/iqa/jobs
GET  /v1/iqa/jobs/{job_id}
GET  /v1/iqa/jobs/{job_id}/result
POST /v1/iqa/jobs/{job_id}/cancel
```

Terminal states are `succeeded`, `partial`, `failed`, and `cancelled`. Only succeeded
and partial terminal jobs resolve published schema-v2 results. Completion never
auto-opens Results. Create is not blindly retried; result-reference recovery is bounded
and idempotent.

### Executable PARTIAL result

P5-C extends schema v2 without a version bump:

- `publication_state = "partial"`;
- ordered `scene_outcomes[]` covers every requested Scene;
- failed/cancelled outcomes carry bounded diagnostics;
- at least one Scene succeeds and at least one fails/cancels;
- `scenes[]` contains only fully published successful Scenes in request order;
- successful Scenes satisfy the same schema-v2 numerical/geometry/cardinality
  invariants as COMPLETE.

P5-B Results explores successful Scenes and reports failed/cancelled Scene outcomes.

### Debug/contract harnesses

Debug-only P5-C tools remain gated by `PIXELSCOPE_REMOTE_IQA_DEBUG`:

- Request Inspector;
- Replay JSON;
- deterministic COMPLETE/PARTIAL result generator;
- real-socket localhost HTTP fault harness.

The localhost server is a client protocol test double, not the GPU server.

## P5-C validation authority

PR #42 merged as `main@24b328d02c0cd56fb79920e069af06d6e4cb706f` only after its
storage/lifecycle blockers were closed, independent latest-head review passed, and the
owner reported final full-repository validation PASS.

That is historical P5-C evidence only. It does not validate P5-F changes.

## P5-D completed implementation state

P5-D adds explicit native Scene inspection to the production composition.

### Source locator, decode, and identity verification

Schema-v2 source bindings may add optional `storage_root_id`.

- no schema bump;
- old v2 without the field still opens through P5-B;
- omission disables native Inspect because PixelScope does not guess roots;
- location metadata is excluded from source equality and `measurement_context_id`;
- root-ID validation is shared with P5-C;
- resolution reuses the P5-C existing-source resolver and containment rules;
- ordinary PNG/BMP/JPG/JPEG dimensions use the exact P5-C bounded-header probe;
- every unique native source is decoded from one encoded byte buffer;
- SHA-256 over that exact buffer must equal the published SHA before commit;
- the resulting decoded `ImageDocument` is carried forward as the verified generation;
- all required variant bindings must pass before local mutation;
- repeated variant bindings to the same `source_id` share one native source identity;
- distinct source identities claiming one physical locator are rejected;
- >6-variant-binding native Inspect is rejected without truncation.

### Canonical local workflow

Successful Inspect:

1. reuses already-Registered paths where present;
2. registers any missing verified unique sources through the ordinary input path;
3. advances canonical load tokens so older foreground/preload decodes stale-drop;
4. publishes each exact already-decoded SHA-bound generation under its canonical
   document ID, accounts/touches it through the normal residency owner, and invalidates
   dependent source-view cache identity when source content changed;
5. only after every verified unique-source generation is present, selects those unique
   sources through the canonical Selected/current-page path so first presentation and
   native analysis observe the verified generation;
6. enforces normal residency eviction after current-page protection exists;
7. leaves normal residency/preload/Difference/analysis ownership unchanged.

Repeated variant bindings that share one native `source_id` still retain every IQA
variant identity. The one canonical Files/native document gets a bounded
**Shared-source spatial binding** selector so overlay and Block Inspector can switch
between the aliased variant fields without duplicating local image identity.

P4-A temporary Picks block initial Inspect. A new Pick made after Inspect is preserved
and invalidates Return rather than being silently cleared by restoration.

### Return lifecycle

The first successful Inspect captures a transient Selected-order / page-anchor /
applicable Active / applicable Primary / layout snapshot. Linked Scene navigation does
not replace this first target.

Return explicitly re-commits the captured page after canonical selection reset. Single
View restores the actual displayed Active source; Multi View restores applicable
Primary and then activates the captured Active tile.

Newer non-IQA Selected/Files/layout/Primary or temporary Pick intent invalidates
Return. Active alone is not an invalidation trigger. The snapshot is not Session v1
persistence.

### Spatial inspection

P5-D reuses the existing schema-v2 Scene grid loader and math:

- Absolute cell value = `S1/W`;
- Relative power = canonical raw target/reference dB;
- Relative signed = raw target-reference delta;
- invalid/pair-invalid cells stay invalid;
- no quality-direction sign flip is applied to the raw spatial field.

Existing affine/grid geometry maps analysis cells to source polygons and source cursor
points back to grid cells. Drawing and hit-testing share non-zero grid origins,
non-integer transforms, valid rectangles, and discarded borders.

Overlay is vector/block based on existing `ImageViewer.view_box`; no full-resolution
heatmap/alpha buffer or secondary viewer/source authority is introduced.

Block Inspector exposes bounded W/S1/S2/count/valid/mean/reference/pair/geometry data.
For a shared native source, the Shared-source spatial binding selector changes the
active aliased `variant_id` used by both overlay painting and Block Inspector while the
canonical Files document remains unchanged.

### Async/stale safety

Verification and grid work use feature-local workers. Generation, result identity,
Scene, local intent, settings revision, and spatial request identity gate publication.
New Result open and shutdown cancel feature-local work and clear overlays.

Remote IQA logical-root mappings are live settings. A mapping change increments the
P5-D locator revision, cancels pending native verification under the older mapping,
and refreshes Inspect availability before any later callback can publish.

## P5-D validation status

P5-D completed its exact-head automated/manual/review gates and merged as PR #43 at
`main@b086443d188eb9daae4bbf4f0faab3ff1d114f93`.

Its focused regression files remain:

```text
tests/unit/test_p5d_scene_inspection.py
tests/unit/test_p5d_source_locator_identity.py
tests/unit/test_p5d_review_closeout_unit.py
tests/ui/test_p5d_viewer_linked_inspection.py
tests/ui/test_p5d_stale_inspection.py
tests/ui/test_p5d_review_closeout.py
tests/ui/test_p5d_alias_spatial_binding.py
```

The complete contract and historical validation matrix remain in
[`P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md). P5-D PASS is not inferred as
P5-F PASS.

## P5-E completed historical workflow

P5-E / PR #44 is merged at
`main@6a0a334d61a7495b9c3433edfcbd537c8df59468`.

It adds the separate max-10 Recent IQA Results history, production logical/local Result
locators, pre-presentation `result_id + schema_version` identity checking, result-only
mode, passive Provenance, live root-remap observation, and stale logical-Recent resolver
protection while preserving P5-B canonical opening, P5-D Inspect, Session v1, and P4-C
Recent ownership.

Its exact durable contract is
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md). P5-E validation remains
historical evidence only.

## P5-F completed repository-side hardening state

P5-F follows **measure before optimizing** but is now explicitly scoped to evidence that
can be obtained without the unavailable real GPU/SMB environment.

Repository characterization identified and corrected two ownership/lifetime problems:

- P5-B Result/Reference, P5-D verification/spatial, and P5-E historical resolution are
  isolated onto one application-owned max-two Remote IQA result/file pool. The local
  Statistics/Difference analysis pool remains distinct, and P5-C job operations retain
  their own separate max-two pool.
- production HTTP reuse now uses a lazy proxy. Merely queuing a P5-C operation creates
  no physical `HttpIqaJobClient`; checkout occurs only when the worker performs its first
  HTTP operation. Queued work cleared before execution therefore owns no HTTP resource.

Independent review also tightened the compatibility probe so a non-terminal cancel
response continues polling and a succeeded/partial terminal state remains recorded even
when later Result-reference fetch fails.

Focused regressions cover production pool binding and a four-job/max-two-worker
shutdown case, proving queued work does not create extra physical clients and executing
leases drain after shutdown.

No raw-grid cache, grid preload, adaptive polling, generalized retry, new user Settings,
WebSocket, or optional detail viewer is added without real-environment evidence.

Historical owner validation on implementation head
`f9a81b008d660405fc01e775607d78a91676093e` records focused P5-F, docs, Ruff,
mypy, pip, and diff PASS. Full Windows offscreen pytest records 925 passed, 1 skipped,
and three Qt/pyqtgraph UI failures. Those exact three nodes reproduce identically on
implementation base `main@6a0a334d61a7495b9c3433edfcbd537c8df59468`
under the same environment (`3 failed in 8.72s`), satisfying the independent review's
requested baseline comparison. They are pre-existing/offscreen validation debt rather
than a P5-F regression. No full-suite PASS is claimed. Independent implementation and
architecture review passed, and P5-F merged as PR #45 at
`main@6634447fc3c48545a2482718dd3f444928806218`.

## P5-G deferred external validation state

P5-G **External GPU/SMB Validation & Closeout** is the final P5 program gate and is
deferred for realistic environment availability, not because repository-side client
implementation is missing. Its authoritative deferred execution plan is
[`exec-plans/deferred/p5g-external-gpu-smb-validation.md`](exec-plans/deferred/p5g-external-gpu-smb-validation.md).

It will validate the real external GPU API/result writer, mapped/shared storage,
Current Pair/Folder Pair, COMPLETE/PARTIAL, cancel/completion races, historical reopen,
Inspect/spatial flow, concurrent local analysis, lifecycle behavior, and real
network/grid/source timing observations. Any follow-up optimization must remain
measurement-backed and bounded.

No real GPU/SMB PASS has been observed or claimed.

## Forward sequence

```text
R Repository Refactoring & Validation Hardening
    ↓
P5-G External GPU/SMB Validation & Closeout when the environment is available
    ↓
P5 Complete
    ↓
P6 Identity, Access & Remote Operations
    ↓
P7 Release Engineering & Distribution
```
