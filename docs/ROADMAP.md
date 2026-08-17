# Roadmap

## Delivered baseline

### P0/P1 — Product foundation — Complete

PixelScope provides local image registration/selection, one-to-six-image synchronized
comparison, Statistics, Histogram, Line Profile, Difference, Split Channels, RAW
loading, fixed comparison layouts, and stable local viewer/navigation behavior.

P1-D/P1-E/P1-F workspace-polish work completed as PR #10–#12.
Historical plan:
[`docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md).

### P2 — Runtime Foundation, Settings & Performance — Complete

Completed sequence:

`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`

Delivered contracts include:

- typed settings schema v5;
- independent Difference/source memory budgets;
- byte-budgeted decoded-source LRU residency;
- bounded Current Comparison Page protection;
- one-position-ahead, max-one speculative Folder Position preload;
- RUNNING preload foreground promotion;
- deterministic sanitized diagnostics;
- bounded application worker ownership and lifecycle expectations.

P2-F merged as PR #20 at
`9c66629f6392971b8c52ac9dff27b16166cf9829`.
Historical plan:
[`docs/exec-plans/completed/p2-runtime-foundation-settings-performance.md`](exec-plans/completed/p2-runtime-foundation-settings-performance.md).

### P3 — Image Semantics & RAW Processing — Complete

P3 established the authoritative local image hierarchy:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset
Current Comparison Page        # max 6
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

Delivered work includes:

- Gray and mixed-bit Difference semantics;
- native RAW authority and Black-anchored presentation gain;
- general Display Gain as presentation-only state;
- large logical Selected sets with six-image Current Comparison Pages;
- unified image/folder opening and lazy RAW profile resolution;
- integration/presentation hardening without Selected-wide eager decode or
  Comparison Page speculative preload.

P3 completed with PR #27 at
`835634a58609601605fd0fc18a3028b64225f535`.
Historical plan:
[`docs/exec-plans/completed/p3-image-semantics-raw-input.md`](exec-plans/completed/p3-image-semantics-raw-input.md).

### P4 — Workflow & Session Productivity — Complete

Completed sequence:

`P4-0 → P4-A → P4-B → P4-C → P4-E → P4-F`

P4 delivered:

- large-selection temporary Pick/Keep curation without new source ownership;
- `.pixelscope` Comparison Set v1 compatibility followed by PixelScope Session v1;
- typed Recent Images/Folders/Sessions;
- explicit Difference/source-curation lifecycle alignment;
- focused Statistics/Histogram/Line/Difference result export productivity;
- Session page-anchor, Display Gain lifetime, and repeated-composition hardening.

Important preserved contracts:

- Picks are temporary source IDs and own no residency/preload/analysis work;
- Session persists durable workspace intent, not process/cache/worker state;
- only explicit successful Difference Calculate establishes active Difference state;
- export consumes established results and never becomes numerical authority;
- off-page Selected/Picked sources remain evictable;
- P2 Folder Position preload remains unchanged.

P4-F merged as PR #35; the P4-complete merged baseline is
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`.

Completed P4 plan:
[`docs/exec-plans/completed/p4-workflow-session-productivity.md`](exec-plans/completed/p4-workflow-session-productivity.md).

Deferred from P4, not completion blockers:

- saved/named/multiple ROI management;
- Alpha Overlay / Flicker / Wipe;
- arbitrary-angle Line Profile with an explicit sampling contract.

## Forward sequence

`P5 Remote IQA Platform`
→ `P6 Identity, Access & Remote Operations`
→ `P7 Release Engineering & Distribution`

P5 is now the active program.

Active execution plan:
[`docs/exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

Remote IQA durable contract:
[`docs/REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

# P5 — Remote IQA Platform — Active

## Product objective

P5 connects the local PixelScope engineering workflow to an external GPU Image
Quality Assessment service.

The intended experience is:

```text
fast local PixelScope inspection
        ↓ when needed
submit current pair or large folder-pair IQA
        ↓ non-modal remote job
continue local work
        ↓
open durable IQA result
        ↓
dataset overview
        ↓
attribute trend / outliers
        ↓
scene
        ↓
spatial block inspection in existing viewer
```

Remote IQA is a parallel feature-local result domain. It does not replace or extend
`Registered → Selected → Current Comparison Page → Presented → Resident` as a source
ownership hierarchy.

## P5 remote data model

The target server/result model is scene-based rather than pair-result-only:

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

P5 v1 UI supports two sources per Scene. Result/request schema should remain
N-source-ready.

The server creates a representative image for each Scene, then derives common
continuous structural context using PiDiNet Edge Map plus a texture-network Texture
Gate. Exact soft/hard weighting policy is server configuration authority; PixelScope
does not reconstruct effective numerical weighting from those maps.

## IQA attributes

Initial attributes and current server-default block sizes are:

| Attribute | Direction | Current default block |
|---|---|---:|
| Luma noise | lower is better | 32×32 px |
| Luma detail | higher is better | 32×32 px |
| Chroma noise | lower is better | 32×32 px |
| Chroma detail | higher is better | 32×32 px |
| Edge strength | higher is better | 32×32 px |
| Luma contrast | higher is better | 128×128 px |
| Luma bias | signed / neutral | 128×128 px |
| Chroma contrast | higher is better | 128×128 px |
| Chroma bias | signed / neutral | 128×128 px |
| Colorfulness | higher is better | 128×128 px |

These block sizes are result metadata, not PixelScope constants.

The server provides weighted mean/std and two distinct official aggregate views for
power attributes:

1. ratio of weighted means;
2. mean of per-grid log ratios.

Bias remains signed-value comparison rather than ordinary dB quality scoring.

## Remote analysis domain

For performance, 4K-class RGB input is processed in an approximately 2K remote
analysis domain. Structural maps, attribute maps, weights, and grids therefore need
explicit transform/valid-rect/grid metadata so PixelScope can map compact IQA blocks
back to original source coordinates. A fixed resize factor is not assumed.

Pairs require matching dimensions; mismatch fails rather than silently changing
comparison geometry.

## Result and bandwidth strategy

P5 uses three result tiers:

1. small durable job manifest/summary for overview/trends;
2. compact scene-level block data loaded lazily for normal spatial inspection;
3. optional large per-pixel 2K detail artifacts loaded only on demand.

Numeric matrices should use compact NumPy-friendly artifacts rather than nested JSON
float lists. Historical results are durable engineering records and should be
reopenable without rerunning GPU analysis.

## Shared storage and HTTP direction

Client and GPU server may see the same SMB/network storage through different physical
paths. P5 uses a logical storage-root ID + relative path instead of embedding local
Windows or server Linux paths in the API.

The existing external server has a blocking HTTP interface. P5 targets an
asynchronous submit/status/result/cancel job API with polling as the initial progress
mechanism. WebSocket progress is optional future work, not a P5 v1 dependency.

## UX direction

P5 should add one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
└─ Results
```

- Current Pair reuses an already-open PixelScope pair without making the user browse
  for the same images again.
- Folder Pair prepares a deterministic sorted pair list and shows Pair Preview before
  submission; count mismatch blocks submission.
- large batch inputs remain IQA references and are not eagerly Registered/Selected;
- completed jobs do not forcibly replace the user's current workspace;
- passive result browsing does not mutate Selected;
- explicit Inspect Pair loads only the chosen Scene pair through the canonical local
  registration/selection path;
- IQA Reference is separate from PixelScope Primary;
- result navigation drills down from dataset overview → attribute → scene → block.

# P5 execution sequence

`P5-0 → P5-A → P5-B → P5-C → P5-D → P5-E → P5-F → P5 Complete`

## P5-0 — P4 Closure & P5 Program Setup — Active

Docs-only orchestration slice.

Goals:

- record PR #35/P4 as complete;
- archive the P4 active plan;
- establish the P5 execution plan and Remote IQA contract;
- reconcile ROADMAP/CURRENT_STATE/UI status;
- define implementation/review/validation policy before runtime work;
- add no P5 runtime/UI behavior and change no Settings/Session schema.

## P5-A — Contract Fixtures & IQA Domain — Planned

Build the contract before the live server integration:

- versioned Job/Scene/Source/Attribute/result schemas;
- manifest/summary/compact-scene parser;
- deterministic production-shaped mock GPU result generator;
- local numerical recomposition utilities;
- error/corruption/missing-artifact handling.

The first sample fixture is approximately 10–12 scenes × 2 sources and all ten
attributes. It deliberately includes trends, spatial outliers, signed bias,
near-zero values, a case where the two official aggregate methods differ, dynamic
grid metadata, non-zero origin/discarded border, transform metadata, soft/hard
weighting provenance variants, and missing/corrupt artifact cases.

Large real 2K maps are not committed as test fixtures.

## P5-B — IQA Workspace & Local Result Exploration — Planned

Prove the product UX entirely from deterministic fixtures before connecting the live
server:

- non-modal IQA workspace;
- Open IQA Result...;
- Attribute × Scene overview;
- selected-attribute trend/outlier navigation;
- aggregation-mode switching;
- clean close/recreate behavior;
- no passive Files/Selected mutation.

## P5-C — Submission & Shared Storage — Planned

Connect the proven result workflow to the external service:

- logical shared-storage root mapping;
- safe staging for local-only input;
- Current Pair submit;
- Folder Pair + Pair Preview;
- explicit Scene manifest;
- HTTP submit/status/result/cancel;
- polling progress and non-modal Jobs UI;
- failures/cancel without local workspace mutation.

GPU server implementation remains outside this repository.

## P5-D — Viewer-linked Scene Inspection — Planned

Connect IQA anomalies to source image locations:

- explicit Inspect Pair;
- canonical loading of only the inspected pair;
- transient return to the previous workspace;
- IQA Reference independent from Primary;
- Scene navigation linked to the existing viewer;
- analysis-domain grid → source → viewer coordinate mapping;
- vector/block overlay and block inspector;
- safe interaction with Difference/Gain/ROI/Line and temporary Pick state.

## P5-E — Historical Result Workflow — Planned

Make completed IQA results reusable:

- durable Open IQA Result...;
- bounded Recent IQA Results;
- immutable job/result/source-hash identity;
- result-only mode when source images are unavailable;
- source/hash mismatch diagnostics;
- provenance display;
- evaluate Session persistence of lightweight result reference/selection intent only.

P6 remains responsible for authentication, SSO, credentials, permission, audit admin,
and server-side access policy.

## P5-F — Integration & Performance Hardening — Planned

Validate the composed workflow against the real server and large datasets:

- real API/result compatibility;
- lazy scene/result loading and bounded local cache behavior;
- SMB/network bandwidth characterization;
- current-pair and large-folder stress;
- cancellation/failure/missing artifacts;
- stale callback and application close/recreate safety;
- proof that batch membership does not become local source/residency/preload
  authority;
- optional detail-artifact characterization;
- P5 closure documentation.

No fixed wall-clock latency is a correctness merge gate. Correctness gates are
versioned identity, bounded ownership, lazy loading, no duplicate work, stale-result
rejection, and teardown safety.

# P6 — Identity, Access & Remote Operations

Planned after P5:

- Login / SSO;
- token and credential lifecycle;
- permission/access policy;
- user/project/purpose audit integration;
- operational administration and controlled result cleanup.

P5 result schemas may reserve provenance metadata fields but do not implement these
security/administrative authorities.

# P7 — Release Engineering & Distribution

Planned after P6:

- exactly PyInstaller 5.7 `onedir`;
- portable ZIP;
- Inno Setup;
- clean-PC smoke testing;
- signing;
- update strategy;
- repeatable release process.

## Deferred optimization outside the phase sequence

Schedule only when profiling/user-visible latency demonstrates need:

- broader source preload concurrency/direction changes;
- CPU/I/O aggressiveness controls;
- broader resource-policy Settings exposure;
- process-level profiler telemetry;
- native/SIMD display-gain optimization;
- eager/full download of 2K IQA maps;
- WebSocket job progress when polling proves insufficient.