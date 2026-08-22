# PixelScope current state

Snapshot date: 2026-08-22
Current merged executable-v2 baseline / P5-A2 Stage 2 PR #40 merge commit:
`5fcea48bd80e7a9aa5f5caa42fdaabebb27256d6`

P4 **Workflow & Session Productivity**, P5-0 **P4 Closure & P5 Program Setup**, P5-A
**schema-v1 Contract Fixtures & IQA Domain**, and P5-A2 **schema-v2 durable +
executable migration** are Complete.

P5 **Remote IQA Platform** is Active in P5-B **IQA Workspace & Local Result
Exploration** / PR #38. P5-B is rebased on the executable-v2 main baseline and is a
merge candidate pending fresh validation/re-review of the narrow latest reviewer
fixes. P5-C **Submission & Shared Storage** is the next planned slice after P5-B
closes.

Active plan:
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

P5 durable product/data contract:
[`REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Current P5 numerical/result target:
[`REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).

Historical merged schema-v1 baseline:
[`REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).

Completed P4 plan:
[`exec-plans/completed/p4-workflow-session-productivity.md`](exec-plans/completed/p4-workflow-session-productivity.md).

## Merge baseline

- P1-D/P1-E/P1-F completed as PR #10–#12.
- P2-0 through P2-F completed as PR #13–#20; P2-F merged at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.
- P3 completed with P3-E / PR #27 at
  `835634a58609601605fd0fc18a3028b64225f535`.
- P4-0 P3 Closure & P4 Program Setup merged as PR #28.
- P4-A Review Selection & Curation merged as PR #29 at
  `3486146494076e9b513843b90ec44e504043729e`.
- P4-B Comparison Set Persistence merged as PR #30 at
  `3a19589e6cbad5fa8c814c522df6a553f59ee340`.
- P4-C Session Persistence & Typed Recent merged as PR #31 at
  `436033a0d99513fe8db35f08305395127e430af2`.
- PR #32 Display Gain/Difference runtime stabilization merged at
  `e1ccf264f86e37b438c923faceae96c3ecb539b7`.
- PR #33 Difference/source-curation lifecycle merged at
  `51a540c92c372d71e02fd849fb5e0d406d0e9327`.
- P4-E Analysis Export Productivity merged as PR #34 at
  `79ee74134f1ebef9dd13f82e49f8e34407bb78f4`.
- P4-F Integration & Workflow Hardening merged as PR #35 at
  `d1d1fbe8fc7ee81855e5e037bcecc1278435e298`.
- P5-0 P4 Closure & P5 Program Setup merged as PR #36 at `ee7ca03`.
- P5-A Contract Fixtures & IQA Domain / schema v1 merged as PR #37 at
  `fceb16f6e43c48ec65fbf7ebbcc103b56716b686`.
- P5-A2 Stage 1 schema-v2 durable contract merged as PR #39 at
  `4f2d58f36152cbebd1110a2aed09afacc6f09596`.
- P5-A2 Stage 2 executable schema-v2 migration merged as PR #40 at
  `5fcea48bd80e7a9aa5f5caa42fdaabebb27256d6`.

P5-A provides the historical Qt-free schema-v1 published-result domain, safe bounded
manifest/summary/compact reader, deterministic W/S1/S2/count/valid recomposition,
continuous geometry utilities, and production-shaped fixtures. That implementation
remains useful as read-only historical compatibility but is not the current numerical
target after the schema-v2 decision.

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
- **Presented** is current viewer representation of the page/context.
- **Resident** is decoded native source retained only under P2 source-residency
  policy while a correctness/runtime owner requires it.

`Analysis Working Set = Current Comparison Page`.

Viewer slot numbers are local `1..6` inside the Current Comparison Page; global
Selected ordinal and local viewer slot are distinct concepts.

## Current input policy

Supported local PixelScope image inputs remain exactly:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

- **Open Images...** and direct-file drag/drop are selection-oriented.
- **Open Folder...** and folder drag/drop are registration-oriented.
- Folder registration does not replace Selected or presentation state.
- Registered-but-unselected is a valid workspace state.
- unresolved folder RAW remains lazy until foreground intent requires profile
  resolution.

P5 batch references must not change these rules. A large IQA batch is not implicitly
Registered/Selected/decoded.

The current remote-submission baseline remains PNG/JPG/JPEG/BMP only with no silent
RAW conversion until P5-C explicitly changes the request contract.

## P2 runtime/resource contracts

P5 inherits and must not accidentally redesign:

- exact native `source.nbytes` decoded-source residency accounting;
- independent source and Difference memory budgets;
- bounded current-page/correctness source protection;
- off-page Selected/Picked sources remaining evictable;
- Folder Position `+1` preload only, max-one speculative preload worker;
- RUNNING preload promotion rather than duplicate foreground work;
- application-owned bounded heavy-analysis/Display Gain workers;
- request identity, stale-result rejection, and close/recreate safety.

Remote IQA transport/result callbacks are feature-local asynchronous work and must
compose with these lifetime rules rather than acquire source ownership.

Schema-v2 grid loading is not tied to source residency. P5-B uses a bounded
feature-local Reference-preparation policy and does not turn batch sources into
decoded local source ownership. Final grid-cache/preload tuning remains P5-F.

## P3 image-analysis semantics

Native `ImageDocument.source` remains authoritative for local analysis.

- Display Gain is presentation-only.
- RAW Black/White/display transforms do not redefine native analysis.
- Difference remains native code-domain for equal effective bit depth and
  independently normalized `[0,1]` for mixed effective depth.
- Statistics, Histogram, Line Profile, local Difference, and Split Channels retain
  their existing domains and Current Comparison Page behavior.

Remote IQA is a separate server-authored measurement domain. Remote IQA values must not
be presented as native PixelScope Statistics/Difference output.

## P4-A temporary curation

P4-A remains source-only temporary workflow state:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
direct temporary Pick Set
    ↓ Keep Selection
new Selected subset
```

Picks own no decode/residency/protection/preload/analysis/Difference work and are not
persisted. Keep Selection is the only curation operation that mutates logical
Selected.

P5 passive result browsing must not invalidate Picks. A later explicit P5 Inspect
operation intentionally changes Selected, so conflicting Inspect entry remains blocked
while an active curation baseline exists rather than silently clearing Picks.

## Difference lifecycle

PR #33 remains active Difference authority:

- only explicit successful **Calculate** establishes active Difference provenance;
- hide/show is visibility-only for that established result;
- passive navigation/cache presence never promotes another result;
- Keep Selection tears active Difference down before Selected mutates;
- generation-aware cache entries are not indiscriminately purged by curation.

P5 IQA overlay/comparison data is not Difference data and must not share Difference
cache identity, toolbar state, or establishment rules.

## Session and Recent

PixelScope Session v1 persists durable local workspace intent:

- Registered membership + RAW reconstruction metadata;
- exact ordered Selected paths;
- Current Comparison Page anchor;
- applicable Active/Primary/layout;
- ROI/Line/Display Gain/applicable Split state;
- only an eligible regenerable Difference recipe.

It does not persist decoded arrays, caches, workers/tokens, or P4-A Picks.

Current typed Recent categories are Images, Folders, and Sessions. P5-E plans a
separate bounded Recent IQA Results workflow. P5 treats remote results as external
immutable references; embedding remote numeric arrays into Session remains out of
scope.

## P4 export

Current focused exports remain consumers of already-established local results:

- Statistics CSV;
- Histogram CSV;
- Line Profile CSV;
- Difference metrics CSV/copy;
- settled active Difference presentation PNG.

P5 result export is not implicitly provided by these actions. Future remote-IQA export
must consume the remote result repository without changing local numerical/source
authority.

## P5 current result architecture — executable schema v2

The active executable contract is:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

```text
IQA Result
    ↓
ordered variants[]
    ↓
Scene / measurement context
    ├─ exactly one binding per variant for normal complete results
    ├─ representative image / common structural context
    ├─ PiDiNet Edge Map / Texture Gate
    └─ per-variant source measurement
         ├─ fast absolute Scene/dataset summaries
         └─ grid W/S1/S2/count/valid
                ↓ PixelScope
           selected Reference
                ↓
           local target/reference comparison
                ↓
      Dataset Overview / Scene Trend / spatial grid
```

### Identity

- `variant_id` identifies one comparison group/configuration and Reference slot across
  Scenes.
- `source_id` identifies one concrete source image.
- `scene_id` identifies the Scene.
- `measurement_context_id` scopes the published weighted measurement to the Scene
  context that produced its representative/structural/weighting state.

A concrete `source_id` may recur across different Scenes or multiple variant slots in
the same Scene when its `relative_path`, SHA-256, width, and height are identical.
Every complete Scene still binds each declared `variant_id` exactly once. The repeated
source does not collapse variant identity or authorize reuse of weighted measurements.

An absolute source measurement is reference-independent within that Scene context; it
is not globally context-free. The same source hash evaluated under another incompatible
cohort/context is not automatically the same published weighted measurement.

Comparable variants for one Scene/attribute carry exactly equal physical
SceneGeometry/GridGeometry. PixelScope does not index-zip, align, or resize
incompatible grids.

### Ten initial attributes

- Luma noise — lower is better;
- Luma detail — higher is better;
- Chroma noise — lower is better;
- Chroma detail — higher is better;
- Edge strength — higher is better;
- Luma contrast — higher is better;
- Luma bias — signed/neutral;
- Chroma contrast — higher is better;
- Chroma bias — signed/neutral;
- Colorfulness — higher is better.

Current server defaults use 32×32 analysis pixels for noise/detail/edge and 128×128
for contrast/bias/colorfulness, but grid dimensions are remote metadata rather than
PixelScope constants.

### Server measurement authority

For every source/attribute/grid the server publishes normative:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid_mask
```

The canonical Scene absolute mean is `ΣS1/ΣW`; weighted population std is recomposed
from W/S1/S2. Server-written Scene/dataset mean/std summaries are fast projections and
must agree with the normative accumulators within the schema-v2 tolerance or the
artifact is corrupt.

### Absolute dataset summaries

Schema v2 publishes both:

- pooled weighted mean/std across valid Scene measurements;
- equal-Scene mean/std across canonical Scene means.

**Current owner default for absolute Dataset Overview: `pooled_weighted_mean`.**

### Local relative comparisons

Reference selection targets `variant_id`. Pair-valid support is target-valid ∩
reference-valid on a validated common grid.

Power modes are:

1. ratio of pair-valid aggregate weighted means;
2. unweighted arithmetic mean of **finite** pair-valid grid log-ratios.

For mode 2, an undefined/non-finite individual grid ratio such as epsilon-zero `0/0`
is omitted if another pair-valid grid ratio is finite. If no finite ratio remains,
Mode 2 is invalid. Negative power-domain input remains invalid and is not skipped.

Signed attributes use pair-valid weighted target mean minus reference mean. One
Qt-free comparison authority also maps raw values to quality direction: higher-is-
better keeps raw, lower-is-better negates raw for both power modes, and signed/neutral
quality is N/A.

**Current owner default for relative Dataset Overview:** compute the selected
comparison independently per valid Scene, then arithmetic-mean the valid Scene
comparison values.

### Remote analysis domain

4K-class RGB input is analyzed after downscale to an approximately 2K remote domain.
Grid/structural/attribute output requires explicit transform, valid rectangle, grid
origin, block size, and border metadata to map results to source/viewer coordinates.
The continuous pixel-edge/half-open geometry contract proven in P5-A remains active.

### Result artifact categories

1. small `manifest.json` + `summary.npz` metadata for immediate absolute Dataset/Scene
   views;
2. compact absolute Scene-grid measurement NPZ artifacts for local relative/spatial
   work;
3. optional opaque detail/debug references whose typed decode contract is deferred.

Ordinary v2 open performs filesystem I/O for manifest + summary only. Scene grid and
detail references receive syntax validation at open; actual Scene-grid filesystem/
archive/array validation occurs on `load_grid_scene()`.

Grid loading/cache behavior remains a bounded, non-blocking performance policy and may
be measured/optimized later. Historical result reopen remains first-class because
rerunning GPU evaluation is unnecessary and undesirable.

### Safety envelope

V2 freezes bounded manifest/NPZ/cardinality parsing. The aggregate `1024` Scene-source-
binding ceiling is deliberate rather than a cache budget: Stage-1 planning assumed
roughly 300 compared source images, so it supplies >3x headroom while permitting all
512 Scenes for the initial two-variant P5-C workflow. A future larger requirement
needs coordinated schema/safety review rather than a silent override.

### v1 compatibility

P5-A/schema v1 remains explicit read-only compatibility for historical two-source
results/fixtures. New writer/fixture work targets v2. PixelScope never silently
synthesizes v2 absolute source measurements from v1 pairwise summaries.

### Shared storage

Client/server may mount shared SMB/network storage differently. P5 uses logical root ID
+ relative path rather than embedding machine-local paths. Machine-local root mapping
ownership remains a P5-C decision gate.

### PARTIAL direction

Durable PARTIAL results are owner-approved and successful Scene work must be
preservable. Stage 2 intentionally reports v2 PARTIAL as `UNSUPPORTED` until P5-C
freezes detailed missing-variant/per-Scene failure/API/publication/cancel rules.
Unevaluable dimension-mismatched cohorts are rejected/excluded by server evaluation
rather than repaired locally.

### P5-A2 Stage-2 executable additions — Complete / PR #40

PR #40 froze the Stage-1 target into the executable v2 representation and merged at
`5fcea48bd80e7a9aa5f5caa42fdaabebb27256d6`:

- same concrete source identity may recur within/across Scenes when immutable metadata
  is identical; `variant_id` remains comparison-slot identity;
- v2 operator names are reference-neutral:
  `power_ratio_target_over_reference_db` and `signed_target_minus_reference`;
- Mode 2 averages only finite pair-valid per-grid dB values rather than inheriting
  schema-v1 fail-fast behavior for an individual undefined grid ratio;
- one Qt-free comparison authority exposes raw target/reference engineering values
  and quality-oriented values;
- complete v2 requires exact equality of duplicated SceneGeometry and per-attribute
  GridGeometry across variants;
- normal open is summary-first with deferred grid filesystem access;
- optional detail references are opaque in Stage 2 and are not a frozen P5-D decode
  schema;
- `publication_state=partial` is explicitly `UNSUPPORTED` until P5-C defines its
  concrete representation;
- exact arrays/dtypes/shapes, safety ceilings, fingerprint construction, and
  validation behavior are normative in `REMOTE_IQA_V2_SPEC.md`.

## P5-B implemented result workspace — Active / PR #38

P5-B currently implements the local result-exploration slice:

- **File > Open IQA Result...** uses canonical version dispatch;
- v2 opens summary-first and defaults to Absolute measurements;
- Absolute Dataset Overview uses `pooled_weighted_mean` and absolute Scene values use
  published canonical summaries;
- all N-way variants retain stable table/chart order and color across display modes;
- selecting a v2 Reference defers Scene-grid I/O/math to a background worker;
- Reference preparation materializes one Scene grid at a time, derives all applicable
  target/attribute scalar comparisons via executable-v2 helpers, retains only scalar
  results, releases the grid, then advances;
- relative Dataset Overview is the equal-Scene arithmetic mean of valid Scene
  comparison values;
- Relative table/chart keeps the selected Reference as a local presentation-only zero
  anchor while target values remain canonical target/reference engineering values;
- Absolute display mode uses a collision-proof local presentation tag rather than a
  reserved string in the server-owned `variant_id` namespace;
- a failed deferred Reference preparation restores the last successfully presented
  Reference/mode so the combo and visible values cannot disagree;
- Scene cards show published variant/source/path/hash metadata only and do not open
  native source pixels; logical-root/hash-verified source Inspect remains P5-D;
- IQA dock float/dock/maximize/reset reuses the Plots title-bar lifecycle;
- passive result browsing does not mutate Files, Selected, Current Comparison Page,
  Primary, Difference, source residency/preload, native analysis, or Session.

The repository owner reported the requested Windows full/focused pytest and static
validation PASS on `c77169d7db19ac7dd308c5f772d704c305761ba9`. The narrow
post-review collision/failed-reference/docs changes after that head still require
fresh focused/static/docs validation and independent latest-head re-review before
merge. Repository-wide Ruff formatter drift is intentionally deferred to a separate
formatting-only PR rather than expanded into P5-B.

## P5 program status

Execution sequence:

`P5-0 → P5-A(v1) → P5-A2(v2 migration) → P5-B → P5-C → P5-D → P5-E → P5-F`

- **P5-0** — P4 closure + original P5 plan/contract — Complete (PR #36).
- **P5-A** — deterministic schema-v1 fixtures + Qt-free IQA domain — Complete (PR #37,
  `fceb16f6...`).
- **P5-A2 Stage 1** — schema-v2 durable contract revision — Complete (PR #39,
  `4f2d58f...`).
- **P5-A2 Stage 2** — executable v2 domain/fixture/parser/tests/docs migration —
  Complete (PR #40, `5fcea48...`).
- **P5-B** — IQA workspace + local result exploration — Active / merge candidate
  (PR #38; latest reviewer-fix validation + re-review pending).
- **P5-C** — shared storage + submission + HTTP jobs — Planned next.
- **P5-D** — viewer-linked Scene/grid inspection — Planned.
- **P5-E** — historical/recent result workflow — Planned.
- **P5-F** — real-server integration/performance/lifetime hardening — Planned.

## Deferred/future boundaries

Still outside current P5-B runtime scope:

- P5-C submission/jobs/shared-storage configuration/PARTIAL terminal policy;
- P5-D logical-root/hash/native Inspect and spatial viewer overlay/block inspection;
- P5-E Recent IQA Results and production historical reopen workflow;
- P5-F final grid-cache/preload/cancellation/performance policy;
- saved/named/multiple ROI;
- Alpha Overlay/Flicker/Wipe;
- arbitrary-angle Line Profile;
- RAW demosaic/WB/CCM/tone mapping;
- authentication/SSO/token/permission/admin operations (P6);
- packaging/signing/updater/release process (P7);
- eager download of every full 2K IQA pixel map;
- WebSocket progress unless polling proves insufficient.
