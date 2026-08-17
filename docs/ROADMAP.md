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

Active execution/orchestration plan:
[`docs/exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

Remote IQA product/architecture contract:
[`docs/REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Normative P5-v1 numerical/identity/geometry/artifact specification:
[`docs/REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).

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

P5 is orchestrated as multiple reviewable PRs. The P5 orchestrator owns cross-slice
contracts/ROADMAP/decision gates; implementation agents own only delegated slices;
independent review agents inspect the latest branch without editing it. Missing
cross-slice policy is resolved with the repository owner and documented before code
that depends on it proceeds.

## P5 remote data model

The target server/result model is Scene-based:

```text
IQA Job
    ↓
Scene
    ├─ ordered sources[] with stable source_id
    ├─ representative image
    ├─ common Edge Map
    ├─ common Texture Gate
    └─ per-source attribute results
          ↓
     derived comparisons by stable operand IDs
```

P5 v1 UI supports two sources per Scene while the durable schema is N-source-ready.
The common continuous structural context is derived from a representative image using
PiDiNet Edge Map plus the server texture-network Texture Gate. Exact soft/hard
weighting is server-profile authority; PixelScope does not reconstruct weighting from
those visualization maps.

## IQA attributes and frozen v1 comparison semantics

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

Block sizes are result metadata, not PixelScope constants.

P5 v1 freezes these implementation-critical rules in `REMOTE_IQA_V1_SPEC.md`:

- raw power orientation is A/B;
- signed bias orientation is A-B;
- each power AttributeSpec carries its own mandatory stabilization epsilon;
- positive semantic quality delta always means A better; lower-is-better attributes
  invert the raw dB sign;
- Tier-2 compact data carries mandatory W/S1/S2/count/valid sufficient statistics;
- A/B valid grids use the intersection of source-valid cells;
- official power summaries are ratio of aggregate weighted means and the **arithmetic
  mean** of valid per-grid dB values;
- zero-weight/no-valid/non-finite cases use explicit invalid/null+reason state rather
  than JSON NaN/Infinity.

The server remains numerical authority for official results while PixelScope can
recompute local derived views from the contractually sufficient compact data.

## Remote analysis domain and exact spatial convention

4K-class RGB input is processed in an approximately 2K remote analysis domain.
Structural maps, attribute maps, weights, and grids carry explicit geometry.

P5 v1 uses continuous pixel-edge coordinates, half-open cell/valid rectangles, and a
row-major invertible source→analysis 3×3 affine. Grid origin is a pixel edge; only
complete contained blocks are serialized; inverse overlay geometry remains continuous
until the viewer/raster boundary. A fixed resize factor is never assumed.

P5-A must include a non-integer scale plus non-zero crop/grid origin fixture to prove
client/server coordinate agreement rather than only a simple 2:1 resize.

## Remote input and deterministic pair formation

P5 v1 remote submission accepts only PNG/JPG/JPEG/BMP families. Local `.raw` support
does not imply remote RAW support; there is no silent P5 demosaic/conversion path.

`Evaluate Current Pair` requires exactly two eligible native sources on the Current
Comparison Page. A/B follows underlying page/Selected source order and is independent
from Primary, Active, viewer reordering, and Difference presentation.

Folder Pair uses immediate non-symlink files only, case-insensitive eligible suffixes,
Unicode-NFC lexical sorting by `(casefold(name), name)`, index pairing, count-match
requirement, and complete Pair Preview. The explicit Scene manifest freezes the pair
list; the server does not re-sort it.

## Result and bandwidth strategy

P5 uses three result tiers:

1. small durable manifest/summary for overview/trends;
2. compact Scene-level block sufficient statistics loaded lazily for normal spatial
   inspection;
3. optional large per-pixel 2K detail artifacts loaded only on demand.

The result artifact has `kind = pixelscope-iqa-result`, schema v1, safe relative
references, data-only NumPy artifacts, bounded dtype/shape/size validation, and an
immutable publication boundary. `manifest.json` is the complete publication marker;
a job cannot be `succeeded`/openable before required Tier-1/2 artifacts are finalized.

Historical results are durable engineering records and should be reopenable without
rerunning GPU analysis.

## Shared storage and HTTP direction

Client and GPU server may see the same SMB/network storage through different physical
paths. P5 uses a logical storage-root ID + relative path instead of embedding local
Windows or server Linux paths in the API.

The existing external server has a blocking HTTP interface. P5 targets an async
submit/status/result/cancel job API with polling as the initial progress mechanism.
WebSocket progress is optional future work, not a P5 v1 dependency.

## UX direction

P5 adds one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
└─ Results
```

- Current Pair reuses an already-open deterministic pair.
- Folder Pair shows the exact pairing before submission.
- large batch references are not eagerly Registered/Selected/decoded;
- jobs do not forcibly replace the current local workspace;
- passive results do not mutate Selected;
- explicit Inspect Pair loads only the chosen Scene pair through the canonical local
  registration/selection path;
- IQA Reference remains separate from Primary;
- temporary P4-A Picks block conflicting Inspect entry;
- transient Return-to-previous-workspace is invalidated rather than applied over
  newer non-IQA workspace intent;
- result navigation drills down dataset → attribute → Scene → block.

# P5 execution sequence

`P5-0 → P5-A → P5-B → P5-C → P5-D → P5-E → P5-F → P5 Complete`

## P5-0 — P4 Closure & P5 Program Setup — Active

Docs-only orchestration slice.

Goals:

- record PR #35/P4 as complete and archive P4;
- establish P5 ROADMAP/execution/orchestration model;
- establish the broad Remote IQA contract;
- establish the normative P5-v1 spec so P5-A math/geometry/parser behavior is
  deterministic;
- reconcile CURRENT_STATE/UI status;
- add no runtime/UI behavior and no Settings/Session schema change in this PR.

## P5-A — Contract Fixtures & IQA Domain — Planned

Build executable contract semantics before live server integration:

- Qt-free versioned Result/Scene/Source/Attribute/comparison models;
- v1 manifest/summary/compact-scene parser;
- deterministic production-shaped mock result generator;
- local weighted mean/std and comparison recomposition;
- exact source→analysis geometry mapping;
- safe corruption/unsupported-artifact handling.

The main fixture is approximately 10–12 two-source Scenes × all ten attributes and
must cover explicit epsilon/near-zero golden values, A/B signs, signed bias,
W/S1/S2/count/valid recomposition, intersected valid grids, two different official
aggregation outputs, dynamic block size, invalid/null behavior, non-integer affine,
non-zero origin/discarded border, soft/hard provenance, mismatch/corruption/path
safety/publication cases, and optional detail. A separate small 3-source structural
case proves N-source-ready identity. Large real 2K maps are not committed.

## P5-B — IQA Workspace & Local Result Exploration — Planned

Prove the result UX entirely from deterministic P5-A artifacts before live server:

- non-modal IQA workspace;
- the **canonical** Open IQA Result controller/parser path;
- Attribute × Scene overview;
- selected-attribute trend/outlier navigation;
- aggregation-mode switching;
- result-only fixture/local operation;
- no passive Files/Selected mutation;
- lifecycle/close-recreate safety.

## P5-C — Submission & Shared Storage — Planned

P5-C must not start until two owner/orchestrator gates are frozen.

**Gate C1 — machine-local logical storage-root configuration ownership**

Choose whether `storage_root_id → client/UNC path` is typed `ApplicationSettings`
(with explicit Settings schema migration) or another already-authoritative machine-
local configuration mechanism. Result artifacts and Session cannot own this mapping.

**Gate C2 — batch failure granularity**

Define request-level failure, per-Scene unreadable/dimension mismatch behavior,
whether mixed results create a durable `partial` terminal state, and cancel versus
final-publication race semantics.

After gates close, P5-C owns safe staging, deterministic Current Pair/Folder Pair
submission, explicit Scene manifest, HTTP job lifecycle, polling Jobs UI, and handoff
into the same P5-B canonical Open Result path.

GPU server implementation remains outside this repository.

## P5-D — Viewer-linked Scene Inspection — Planned

Connect IQA anomalies to source locations:

- explicit Inspect Pair and Pick-state guard;
- canonical loading of only the inspected pair;
- transient return snapshot with stale-intent invalidation;
- IQA Reference independent from Primary;
- linked Scene navigation;
- exact v1 analysis-grid → source → viewer mapping;
- vector/block overlay and block inspector;
- safe interaction with Difference/Gain/ROI/Line.

## P5-E — Historical Result Workflow — Planned

Make completed results reusable by extending, not replacing, P5-B's canonical result
open path:

- bounded Recent IQA Results;
- production logical-root reopen;
- immutable result/source-hash identity;
- result-only mode when source images are unavailable;
- source/hash mismatch diagnostics;
- provenance display.

P5 does **not** modify Session v1. A future IQA reference inside Session requires a
new explicit Session schema/version decision. P6 remains responsible for auth/SSO,
credentials, permission, audit administration, and access policy.

## P5-F — Integration & Performance Hardening — Planned

Validate the composed workflow against the real server and large datasets:

- real API/result compatibility;
- lazy Scene/result loading and bounded cache behavior;
- SMB/network bandwidth characterization;
- current-pair and large-folder stress;
- cancellation/failure/missing artifacts;
- stale callback and application close/recreate safety;
- proof batch membership does not become local source/residency/preload authority;
- optional Tier-3 detail characterization;
- P5 closure documentation.

No fixed wall-clock latency is a correctness merge gate. Correctness gates are stable
versioned identity/math/geometry, bounded ownership, lazy loading, no duplicate work,
stale-result rejection, and teardown safety.

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