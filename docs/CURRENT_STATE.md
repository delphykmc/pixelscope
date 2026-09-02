# PixelScope current state

Snapshot date: 2026-09-02
Current merged `main`: `0b321ea23cb1493664d0187ea9777b94d9b7e81b`

`main` includes the cumulative P5/R history below plus the release-foundation and
local-workflow hardening merged after R closeout:

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
- R7 / PR #55 — final integration validation and R-program closeout, merged at
  `2f29bf95b8d51c470534cf6decda3033681c75bf`.
- PR #60 — activated the dependency-independent P7 Release Foundation sequence;
- P7-A / PR #61 — PyInstaller 5.7 `onedir` executable foundation;
- P7-B / PR #62 — portable ZIP + Inno Setup distribution;
- P7-C / PR #63 — Owner-local Release Candidate Build & Validation, merged at
  `f3b1437b478e119c425dbf00d627b37f0371889e`;
- WP-A / PR #71 — responsive large-folder registration, merged at
  `a04f70447c5b68be9b5ea694909e4c2b1ecf46c2`;
- WP-B / PR #72 — RAW profile and raw-like binary compatibility, merged at
  `f21416fed49f138a60ca15810a2b23818ced0809`;
- WP-C1 / PR #73 — Native YUV Image Semantics, merged at
  `0b321ea23cb1493664d0187ea9777b94d9b7e81b`.

WP-C2 / PR #74 — **Native YUV Difference** — is the active implementation candidate on
top of this merged baseline and is not yet part of `main`. It adds same-subsampling
YUV444/YUV422/YUV420 Difference over the selected native Y/U/V plane, channel-aware
cache/result identity, and WP-C1 ROI-to-native-chroma mapping reuse. Its latest-head
owner-local automated validation and independent re-review remain merge gates.

P5 **Remote IQA Platform** is complete through P5-F. Overall P5 remains Active because
P5-G **External GPU/SMB Validation & Closeout** is only partially observed: temporary
external transport/job/shared-source preflight is now validated, while real GPU/IQA
computation, schema-v2 result publication, and full GPU/result-writer/SMB qualification
remain deferred and NOT VALIDATED. R **Repository Refactoring & Validation Hardening**
completed through independently reviewed PR #55 and remains historical completed work.
P7 Release Foundation is now the active repository implementation program: P7-C is
Complete and **P7-D Stage 1 — Release Metadata & Manual Publication Foundation** is
active. P7-D Stage 2 notification-only update discovery/integration is deferred until
the relevant provider/access and, when required, P6 authentication contracts are
authoritative.

Current execution pointer:
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

Completed R program record:
[`exec-plans/completed/repository-refactoring-validation-hardening.md`](exec-plans/completed/repository-refactoring-validation-hardening.md).

Durable P5 product/transport contract:
[`REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Current numerical/result contract:
[`REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).

P5-D viewer-linked inspection contract:
[`REMOTE_IQA_VIEWER_INSPECTION.md`](REMOTE_IQA_VIEWER_INSPECTION.md).

P5-E historical-result contract:
[`REMOTE_IQA_HISTORICAL_RESULTS.md`](REMOTE_IQA_HISTORICAL_RESULTS.md).

P5-F integration characterization:
[`REMOTE_IQA_INTEGRATION_CHARACTERIZATION.md`](REMOTE_IQA_INTEGRATION_CHARACTERIZATION.md).

P5-G external validation plan:
[`exec-plans/deferred/p5g-external-gpu-smb-validation.md`](exec-plans/deferred/p5g-external-gpu-smb-validation.md).

Historical schema-v1 compatibility contract:
[`REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).

P7 release-foundation plan:
[`exec-plans/active/p7-release-foundation.md`](exec-plans/active/p7-release-foundation.md).

P7-D Stage 1 publication audit:
[`exec-plans/active/p7-release-publication-audit.md`](exec-plans/active/p7-release-publication-audit.md).

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

Supported local PixelScope image families are:

```text
.png  .bmp  .jpg  .jpeg  .raw  .data  .yuv
```

- `.raw`, `.data`, and `.yuv` remain one **raw-like binary** family. A `.yuv` suffix
  alone does not imply YUV420/YUV422 or any other byte layout.
- WP-C1 adds an explicit native-YUV interpretation for `.yuv`: a JSON with
  `channel_layout=YUV444|YUV422|YUV420`, or the explicit YUV dialog, selects 8-bit
  tightly-packed Y-first + interleaved-UV storage. UV order is fixed; YUV422 requires
  even width and YUV420 requires even width/height.
- Native YUV viewer presentation is fixed BT.601 Full-range RGB, but that RGB preview is
  never numerical authority. Native Y/U/V planes remain authoritative and subsampled
  U/V stay at their native chroma resolution.
- Pixel inspection reports native Y/U/V. Split Channels produces native-resolution
  Y/U/V views. Statistics and Histogram use native per-plane sample cardinality. ROI
  maps from luma coordinates to the referenced chroma footprint, and Line Profile keeps
  chroma values at native luma-coordinate sample positions.
- WP-C2's current candidate extends Difference to YUV444↔YUV444, YUV422↔YUV422, and
  YUV420↔YUV420. It exposes exactly Y/U/V with Y as default and subtracts only the
  selected native plane in the 8-bit code domain. Native U/V Difference maps therefore
  retain native chroma resolution. Mixed subsampling and YUV↔non-YUV Difference are
  rejected; Combined/weighted YUV, chroma resampling, converted-range/matrix, and
  cross-bit-depth YUV Difference remain out of scope.
- A non-YUV RAW JSON on `.yuv`, `.imgprops`, or **Generic RAW profile…** keeps the WP-B
  generic RAW/Bayer path. Same-stem precedence remains explicit PixelScope `.json` >
  `.imgprops` > editable interpretation dialog.
- `.imgprops` maps `width`, `height`, `sensorBitWidth`, `imageType=BAYER<n>`, `pattern`,
  and `pedestal`; unknown producer attributes are ignored and packing is not inferred
  from file size.
- Missing `.imgprops` byte-layout metadata defaults to unpacked `uint16`, little-endian,
  LSB alignment where applicable, offset 0, full-scale white, and
  `minimum_row_bytes()` stride.
- New/default RAW dialog stride tracks the current minimum when width, storage format,
  or container changes until the user edits stride. A user-edited stride and explicit
  JSON stride are manual authority and are not silently replaced by later field changes.
- **Open Images...** and direct-file drag/drop are selection-oriented.
- **Open Folder...** and folder drag/drop are registration-oriented.
- Folder registration does not replace Selected or presentation state.
- Registered-but-unselected is valid.
- unresolved folder raw-like inputs remain lazy until foreground intent requires
  profile resolution and are excluded from speculative preload. Once either a generic
  RAW profile or native YUV profile is resolved, the source reuses the bounded
  Folder-Position preload/promotion, profile-identity, stale-result, residency, and
  Session v1 persistence lifecycle.
- Session v1 retains its existing profile payload field. Its payload is dispatched
  deterministically by `channel_layout` to `RawProfile` or `YuvProfile`; no Session
  schema-version bump is introduced by WP-C1.

Remote IQA submission remains intentionally narrower:

```text
.png  .bmp  .jpg  .jpeg
```

There is no silent RAW/raw-like conversion for Remote IQA.

## P2/P3/P4 authorities inherited by P5

P5 does not redesign:

- exact native decoded-source residency accounting: established ndarray storage for
  RGB/Gray/Bayer and actual Y + U + V native storage for WP-C1 YUV;
- independent source and Difference memory budgets;
- current-page/correctness source protection;
- off-page Selected/Picked sources remaining evictable;
- Folder Position `+1` max-one speculative preload;
- RUNNING preload foreground promotion;
- application-owned bounded analysis/Display Gain workers;
- numerical source authority for local analysis: `ImageDocument.source` for established
  RGB/Gray/Bayer paths and `NativeYuvFrame` planes for WP-C1 YUV; viewer previews remain
  presentation-only;
- Display Gain as presentation-only state;
- explicit Difference commands: Calculate may reuse or compute the current exact
  Difference identity, while toolbar Diff may reactivate only an already-cached result
  owned by the Current Comparison Page; for native YUV that identity includes document
  generation, subsampling/layout, and selected Y/U/V channel. Passive pair/channel
  selection never leaves another identity presented as current;
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
[`REMOTE_IQA_VIEWER_INSPECTION.md`](REMOTE_IQA_VIEWER_INSPECTION.md). P5-D PASS is not inferred as
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
[`REMOTE_IQA_HISTORICAL_RESULTS.md`](REMOTE_IQA_HISTORICAL_RESULTS.md). P5-E validation remains
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

## P5-G external validation state — temporary preflight observed / full qualification deferred

P5-G **External GPU/SMB Validation & Closeout** is the final P5 program gate. The
temporary external server has now provided observed evidence for:

- external connectivity and production create/status transport;
- expected failed terminal stability and cancellation lifecycle;
- failed/cancelled Result non-publication;
- Current Pair Jobs/UI integration;
- mapped-drive/canonical-path shared-root resolution on the client;
- logical root-ID mapping and server-side source verification.

The temporary server then reaches the expected terminal `failed` because IQA computation
is not implemented. This is successful temporary preflight evidence, not a substitute
for real IQA or schema-v2 publication.

The authoritative P5-G execution plan is
[`exec-plans/deferred/p5g-external-gpu-smb-validation.md`](exec-plans/deferred/p5g-external-gpu-smb-validation.md).
Full qualification remains deferred until a real environment can validate IQA/GPU
computation, COMPLETE/PARTIAL schema-v2 publication/result writer, Folder Pair full
end-to-end behavior, historical reopen/remap, native Inspect/spatial flow, complete
shared-root/staging/SMB behavior, coexistence/lifecycle behavior, and real
network/grid/source timing observations.

No full GPU/SMB P5-G PASS has been observed or claimed.

## P7 release-foundation state

P7-0/P7-A/P7-B/P7-C are complete. PR #63 merged P7-C's repository-owned Windows
candidate pipeline and preserved the corporate security boundary around production
publication. P7-D is intentionally split rather than expanded into new phases:

- **P7-D Stage 1 — Release Metadata & Manual Publication Foundation — Active.**
- **P7-D Stage 2 — Notification-only Update Discovery/Integration — Deferred pending
  provider/access authority.**

Stage 1 adds no runtime/network behavior. Stage 2 must obey the durable rule **Update
discovery must never initiate authentication**. Stage 1 does not establish whether the
eventual provider requires application authentication. If it does, only an already-
established approved P6 capability may be used and discovery otherwise skips silently;
if an authoritative provider is usable without application authentication, that path
remains permitted. No common-IdP topology is established by Stage 1.

P6 production integration remains sequenced after P5-G. A P6-0 contract audit/research
may begin earlier if authoritative corporate identity/authentication documentation
becomes available, but that research must not implement production authentication or
invent server/token contracts.

## Forward sequence

```text
P7-C Owner-local Release Candidate                 COMPLETE — PR #63
    ↓
P7-D Stage 1 Release Metadata & Manual Publication ACTIVE
    ↓
P5-G External GPU/SMB Validation                   IN PROGRESS — temporary preflight observed; full qualification deferred
    ↓
P6 Identity, Access & Remote Operations            PLANNED / production integration gated
    ↓
P7-D Stage 2 Notification-only Update Discovery    DEFERRED — provider/access authority pending
    ↓
P7-E Final Release Qualification                   DEFERRED
```
