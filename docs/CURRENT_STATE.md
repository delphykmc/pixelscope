# PixelScope current state

Snapshot date: 2026-08-17
Current merged baseline / PR #35 merge commit:
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`

P4 **Workflow & Session Productivity** is Complete. P5 **Remote IQA Platform** is
Active in the P5-0 docs-only program-setup slice.

Active plan:
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

P5 durable product/data contract:
[`REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

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
- P4-F Integration & Workflow Hardening merged as PR #35; current main is
  `d1d1fbe8fc7ee81855e5e037bcecc1278435e298`.

No P5 runtime/UI implementation is present yet. P5-0 changes documentation only.

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

Supported image inputs remain exactly:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

- **Open Images...** and direct-file drag/drop are selection-oriented.
- **Open Folder...** and folder drag/drop are registration-oriented.
- Folder registration does not replace Selected or presentation state.
- Registered-but-unselected is a valid workspace state.
- unresolved folder RAW remains lazy until foreground intent requires profile
  resolution.

P5 batch folder references must not change these rules. A large IQA batch is not
implicitly Registered/Selected/decoded.

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

Remote IQA transport/result callbacks are new feature-local asynchronous work and
must compose with these lifetime rules rather than acquire source ownership.

## P3 image-analysis semantics

Native `ImageDocument.source` remains authoritative for local analysis.

- Display Gain is presentation-only.
- RAW Black/White/display transforms do not redefine native analysis.
- Difference remains native code-domain for equal effective bit depth and
  independently normalized `[0,1]` for mixed effective depth.
- Statistics, Histogram, Line Profile, local Difference, and Split Channels retain
  their existing domains and Current Comparison Page behavior.

Remote IQA is a separate server-authored result domain. A remote IQA value must not
be presented as if it were native PixelScope Statistics/Difference output.

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

P5 passive result browsing must not invalidate Picks. P5 Inspect Pair will eventually
mutate Selected intentionally, so P5 v1 must define a safe conflict rule; the active
plan currently chooses to block conflicting Inspect entry rather than silently clear
an active curation baseline.

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
separate bounded Recent IQA Results workflow. P5 will first treat remote results as
external immutable result references; embedding remote numeric arrays into Session
is explicitly out of scope.

## P4 export

Current focused exports remain consumers of already-established local results:

- Statistics CSV;
- Histogram CSV;
- Line Profile CSV;
- Difference metrics CSV/copy;
- settled active Difference presentation PNG.

P5 result export is not implicitly provided by these actions. Any future remote-IQA
export must consume the remote result repository without changing local numerical
or source authority.

## P5 starting architecture

The planned remote domain is:

```text
IQA Job
    ↓
Scene
    ├─ Source A
    ├─ Source B
    ├─ future Source C ...
    ├─ representative image
    ├─ common Edge Map
    ├─ common Texture Gate
    └─ per-source attribute results
          ↓
     derived comparisons
```

P5 v1 UI supports two-source Scenes but the durable schema/result shape should be
N-source-ready.

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

### Common scene structure and weighting

The external GPU pipeline creates a representative image from the Scene and derives
common continuous PiDiNet Edge Map and texture-network Texture Gate data. Effective
soft/hard region weighting remains server configuration authority.

PixelScope must not reconstruct official weighting from the visualization maps. The
server's official statistics/compact block values are authoritative.

### Statistics

The server provides weighted mean and weighted population standard deviation and two
official aggregate comparison views for power-like attributes:

- ratio of weighted means;
- mean of grid log-ratios.

Bias uses signed values and must remain distinct from dB power-ratio quality metrics.

### Remote analysis domain

4K-class RGB input is analyzed after downscale to an approximately 2K remote domain.
Grid/structural/attribute output therefore requires explicit transform, valid-rect,
grid-origin, block-size, and border-discard metadata to map results back to original
viewer coordinates. Pair source dimensions must match or evaluation fails.

### Result tiers

P5 plans:

1. durable small manifest/summary for overview/trends;
2. lazy compact scene block artifacts for normal spatial inspection;
3. optional large 2K per-pixel detail artifacts for explicit future/detailed use.

Historical result reopen is a first-class requirement because repeated GPU evaluation
is unnecessary and undesirable.

### Shared storage

Client and server may mount the same SMB/network storage differently. P5 will use a
logical storage-root ID + relative path contract instead of embedding machine-local
`G:\...` versus server `/home/data/...` paths in the API.

### HTTP/job direction

The external server currently has a blocking HTTP interface that returns a result
location after completion. P5 targets asynchronous submit/status/result/cancel job
semantics with polling first. WebSocket progress is not initially required.

Typical current 4K-class server extraction is approximately two seconds per source,
so batch execution must be non-modal.

## P5 UX plan

One non-modal IQA workspace/dock is planned:

```text
IQA
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
└─ Results
```

- Current Pair reuses an already-open two-image comparison.
- Folder Pair resolves/shows deterministic sorted index pairing before submission.
- count mismatch blocks batch submission.
- completed jobs do not forcibly replace the local workspace.
- passive IQA result selection does not mutate Selected.
- explicit Inspect Pair loads only the selected Scene pair using existing local
  registration/selection paths.
- IQA Reference is feature-local and separate from Primary.

Results drill down from Job/dataset → attribute overview → selected attribute trend
and outliers → Scene → spatial block inspector.

## P5 program status

Execution sequence:

`P5-0 → P5-A → P5-B → P5-C → P5-D → P5-E → P5-F`

- **P5-0** — P4 closure + P5 plan/contract — Active.
- **P5-A** — deterministic contract fixtures + Qt-free IQA domain — Planned.
- **P5-B** — IQA workspace + local fixture result exploration — Planned.
- **P5-C** — shared storage + current/folder submission + HTTP jobs — Planned.
- **P5-D** — viewer-linked Scene/grid inspection — Planned.
- **P5-E** — historical/recent result workflow — Planned.
- **P5-F** — real-server integration/performance/lifetime hardening — Planned.

P5-A deliberately starts with synthetic production-shaped sample results so schema,
statistics, geometry, corruption handling, and future UI can be tested without a
live GPU server.

## P5-0 validation status

P5-0 changes documentation only. Runtime/UI source and tests are unchanged.
Documentation/link checks and `git diff --check` are the relevant merge checks;
unchanged runtime pytest/Ruff/mypy PASS must not be inferred without execution.

## Deferred/future boundaries

Still outside current P5 runtime scope:

- saved/named/multiple ROI;
- Alpha Overlay/Flicker/Wipe;
- arbitrary-angle Line Profile;
- RAW demosaic/WB/CCM/tone mapping;
- authentication/SSO/token/permission/admin operations (P6);
- packaging/signing/updater/release process (P7);
- eager download of every full 2K IQA pixel map;
- WebSocket progress unless polling proves insufficient.