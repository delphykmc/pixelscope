# PixelScope current state

Snapshot date: 2026-08-21
Current merged baseline / P5-A2 Stage 1 PR #39 merge commit:
`4f2d58f36152cbebd1110a2aed09afacc6f09596`

P4 **Workflow & Session Productivity**, P5-0 **P4 Closure & P5 Program Setup**, P5-A
**schema-v1 Contract Fixtures & IQA Domain**, and P5-A2 Stage 1 **schema-v2 durable
contract** are Complete.

P5 **Remote IQA Platform** is Active in **P5-A2 Stage 2 — executable schema-v2
migration**, implemented in Draft PR #40 on
`feature/p5-a2-executable-schema-v2`. P5-B / PR #38 remains schema-dependent and
paused/untouched until Stage 2 is reviewed, validated, and merged to `main`.

Active plans:

- [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- [`exec-plans/active/p5-schema-v2-revision.md`](exec-plans/active/p5-schema-v2-revision.md)

P5 durable product/data contract:
[`REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Current executable numerical/result target:
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
- P4-0 through P4-F completed as PR #28–#35; P4-complete main baseline is
  `d1d1fbe8fc7ee81855e5e037bcecc1278435e298`.
- P5-0 merged as PR #36 at `ee7ca03`.
- P5-A schema v1 merged as PR #37 at
  `fceb16f6e43c48ec65fbf7ebbcc103b56716b686`.
- P5-A2 Stage 1 durable schema-v2 contract merged as PR #39 at
  `4f2d58f36152cbebd1110a2aed09afacc6f09596`.
- P5-A2 Stage 2 is current Draft PR #40 and is not yet merge authority.

P5-A remains the historical Qt-free schema-v1 published-result implementation. It
continues to provide read-only compatibility and the real v1 golden used by Stage-2
version-dispatch regression tests. New writer/fixture/parser work targets schema v2.

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

- Registered is Files/catalog membership and is not limited to six.
- Selected is ordered logical comparison membership and may exceed six.
- Current Comparison Page is a derived bounded maximum-six working set.
- Presented is current viewer representation of the page/context.
- Resident is decoded native source retained only while a P2 correctness/runtime owner
  requires it.

`Analysis Working Set = Current Comparison Page`.

Remote IQA result membership, batch membership, result-grid arrays, and passive result
browsing do not become local source/residency/preload authority.

## Current input policy

Supported local PixelScope image inputs remain exactly:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

The current remote-submission baseline remains PNG/JPG/JPEG/BMP only with no silent
RAW conversion until P5-C explicitly changes the request contract. P5 batch references
do not implicitly register/select/decode local images.

## P2 runtime/resource contracts inherited by P5

P5 must preserve:

- exact native `source.nbytes` decoded-source residency accounting;
- independent source and Difference memory budgets;
- bounded current-page/correctness source protection;
- off-page Selected/Picked sources remaining evictable;
- bounded load/preload/heavy-analysis worker pools;
- request identity, stale-result rejection, and close/recreate safety.

Remote IQA transport/result callbacks are feature-local asynchronous work. Schema-v2
grid loading may later have a feature-local bounded cache, but it does not alter
decoded-source residency ownership.

## P3 image-analysis semantics

Native `ImageDocument.source` remains authoritative for local analysis. Display Gain
is presentation-only. Statistics, Histogram, Line Profile, local Difference, RAW
native semantics, and Split Channels retain their established P3 contracts.

Remote IQA is a separate server-authored measurement domain. Remote IQA values are not
native PixelScope Statistics/Difference output.

## P4 workflow/session contracts inherited by P5

P4-A temporary Picks own no decode/residency/protection/preload/analysis/Difference
work. Keep Selection is the curation action that mutates Selected. Passive IQA result
browsing does not invalidate Picks; later explicit source Inspect must respect the
curation guard.

Session v1 continues to persist durable local workspace intent only. It does not
persist Remote IQA numeric arrays, remote workers/tokens, or batch membership. P5-E
will add a separate bounded Recent IQA Results workflow rather than silently changing
Session v1.

Existing P4 exports consume established local results; they do not automatically
become Remote IQA export authority.

## P5 executable result architecture — schema v2

The active executable target is:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

```text
IQA Result
    ↓ ordered variants[]
Scene / measurement_context_id
    ├─ exactly one source binding per variant for COMPLETE
    ├─ server-owned representative/model/preprocess/weighting context
    └─ per-source absolute measurements
         ├─ summary.npz absolute Scene/Dataset projections
         └─ Scene grid W/S1/S2/count/valid
                ↓ PixelScope
           selected reference variant_id
                ↓
           local target/reference comparison
                ↓
      Dataset Overview / Scene Trend / spatial grid
```

### Identity and context

- `variant_id` is stable comparison/configuration identity across Scenes.
- `source_id` is stable concrete-image identity.
- `scene_id` identifies the evaluation Scene.
- `measurement_context_id` identifies the weighted Scene evaluation context.

The same `source_id` may recur across different Scenes when immutable source metadata
(path identity, SHA-256, width, height) is identical. Matching source identity never
authorizes weighted-measurement reuse across contexts. Duplicate `source_id` binding
inside one complete Scene is explicitly invalid.

The executable context form is `mc2:<64 lowercase sha256 hex>` over canonical JSON
binding ordered source/cohort identity, model/preprocessing/weighting/representative
provenance, and analysis/grid geometry. Geometry floating values are fingerprinted via
`float.hex()` tokens.

### Complete geometry/cardinality

A complete Scene has exactly one source per declared variant in exact top-level variant
order. Source dimensions must match. Stage 2 deliberately requires exact equality of
the duplicated `SceneGeometry` and per-attribute `GridGeometry` metadata across
variants. PixelScope does not create an alignment or tolerance-based correspondence.

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

Grid dimensions are remote metadata rather than PixelScope constants.

### Numerical authority

For every source/attribute/grid, the server publishes normative:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid_mask
```

The canonical Scene absolute mean is `ΣS1/ΣW`. Server-written Scene/Dataset means and
std values are fast projections and must agree with the accumulators within:

```text
abs(a - b) <= max(1e-12, 1e-9 * max(abs(a), abs(b)))
```

Schema v2 publishes both pooled-weighted and equal-Scene absolute Dataset summaries.
The default absolute Dataset Overview remains pooled weighted mean.

### Reference-neutral local comparison

Schema-v2 operators are:

```text
power_ratio_target_over_reference_db
signed_target_minus_reference
```

The v1 A/B strings remain historical compatibility only.

Pair-valid support is target-valid AND reference-valid on the already validated common
grid. Power mode 1 is ratio of pair-valid aggregate weighted means. Power mode 2 is
unweighted arithmetic mean of finite pair-valid grid dB ratios. Signed attributes use
pair-valid weighted target mean minus reference mean.

One Qt-free v2 helper owns both raw engineering orientation and quality orientation:

- higher-is-better power: quality = raw;
- lower-is-better power: quality = -raw;
- signed/neutral: quality N/A.

The same quality rule applies to both power modes. P5-B must consume this authority.

The default relative Dataset Overview remains arithmetic mean of valid per-Scene
selected comparison values.

### Concrete artifacts and summary-first boundary

```text
result/
    manifest.json
    summary.npz
    scenes/<scene_id>.npz
    detail/... optional
```

`summary.npz` Scene arrays use `(scene, variant, attribute)` axes. Dataset arrays use
`(variant, attribute)`. Scene-grid W/S1/S2/count/valid arrays use
`(variant, row, column)`.

Ordinary v2 open performs filesystem I/O for `manifest.json` and `summary.npz` only.
Scene-grid/detail references receive host-independent path syntax validation, but
existence/resolution/content checks are deferred. `load_grid_scene()` resolves and
opens only the requested Scene grid. This avoids O(Scene) SMB stat/resolve traffic on
initial overview open.

Optional `detail_artifacts` are opaque bounded references during Stage 2. P5-D must
freeze a typed/versioned detail sub-schema before consuming Edge Map/Texture Gate or
other per-pixel data.

The exact fields, dtypes, shapes, safety ceilings, and malformed-input rules are
normative in `REMOTE_IQA_V2_SPEC.md`.

### v1 and PARTIAL behavior

The canonical dispatcher reads real schema-v1 results through the existing read-only
reader and does not synthesize v2 absolute data. Unknown future versions are
`UNSUPPORTED`.

Durable PARTIAL results remain a P5 product direction, but their concrete shape is
P5-C work. Stage-2 `publication_state=partial` therefore returns `UNSUPPORTED`, not a
best-effort partial parse and not a complete-result reinterpretation.

## P5 UX direction

One non-modal IQA workspace/dock remains planned/in progress:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

- completed jobs do not forcibly replace local workspace;
- passive result browsing does not mutate Selected;
- small summary metadata renders initial absolute Overview/Scene Trend;
- IQA Reference is feature-local and distinct from Primary;
- relative views derive locally from accepted v2 measurements;
- required grid I/O/calculation remains off the UI thread and stale-safe;
- explicit Inspect later loads only selected Scene sources through canonical local
  authority.

## P5 program status

Execution sequence:

`P5-0 → P5-A(v1) → P5-A2(v2 migration) → P5-B → P5-C → P5-D → P5-E → P5-F`

- **P5-0** — Complete, PR #36.
- **P5-A / schema v1** — Complete, PR #37.
- **P5-A2 Stage 1 / durable schema-v2 contract** — Complete, PR #39.
- **P5-A2 Stage 2 / executable schema-v2 migration** — Active, Draft PR #40.
- **P5-B / IQA workspace + local result exploration** — Paused/schema-dependent,
  existing PR #38 untouched until Stage 2 merges.
- **P5-C** — shared storage + submission + HTTP jobs — Planned.
- **P5-D** — viewer-linked Scene/grid inspection — Planned.
- **P5-E** — historical/recent result workflow — Planned.
- **P5-F** — real-server integration/performance/lifetime hardening — Planned.

## P5-A2 Stage-2 merge gates

PR #40 now contains the executable v2 domain/fixture/parser/reader, neutral comparison
operators, centralized quality semantics, cross-Scene source-reuse validation,
summary-first deferred-grid behavior, and repository-native v2 tests. It remains Draft
until review and repository-pinned validation are observed.

Required validation is recorded in the active P5 schema-v2 execution plan. Only
commands actually observed may be recorded as PASS. The earlier reconstructed-harness
result is not repository merge evidence.

## Deferred/future boundaries

Still outside current P5-A2 Stage-2 scope:

- detailed PARTIAL/failure/cancel taxonomy and logical storage-root ownership (P5-C);
- typed optional detail/overlay consumption (P5-D);
- final grid cache/preload budgets and real SMB performance targets (P5-F);
- authentication/SSO/token/permission/admin operations (P6);
- packaging/signing/updater/release process (P7);
- saved/named/multiple ROI, Alpha Overlay/Flicker/Wipe, arbitrary-angle Line Profile,
  and RAW demosaic/WB/CCM/tone mapping unless separately scheduled.