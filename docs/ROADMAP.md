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

Current P5 numerical/result target:
[`docs/REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).

Historical merged P5-A/schema-v1 specification:
[`docs/REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).

# P5 — Remote IQA Platform — Active

## Product objective

P5 connects the local PixelScope engineering workflow to an external GPU Image
Quality Assessment service.

The intended experience is:

```text
fast local PixelScope inspection
        ↓ when needed
submit current pair or large IQA evaluation
        ↓ non-modal remote job
continue local work
        ↓
open durable IQA result
        ↓
absolute/relative dataset overview
        ↓
attribute Scene Trend / outliers
        ↓
Scene
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

## P5 numerical ownership model — schema v2 target

The merged P5-A/schema-v1 implementation proved the artifact/parser mechanics but was
pairwise-centered. P5-B review exposed that this is the wrong durable center for N-way
Reference switching.

The active target is therefore:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

```text
IQA Result
    ↓
ordered variants[]                 # A/B/C/D comparison-group identity
    ↓
Scene / measurement context
    ├─ exactly one source per variant for normal complete results
    ├─ common representative / structural context
    ├─ common Edge Map / Texture Gate
    └─ per-source absolute measurements
         ├─ fast Scene/dataset summaries
         └─ grid W/S1/S2/count/valid
                ↓ PixelScope
           selected Reference
                ↓
           local target/reference comparison
                ↓
       Overview / Scene Trend / spatial view
```

`variant_id` is stable across Scenes; `source_id` identifies one concrete image.
`measurement_context_id` scopes a weighted absolute measurement to the Scene context
that produced its weighting/gating. The same source hash does not make a weighted
measurement globally reusable across incompatible Scene contexts.

For a normal non-PARTIAL complete result, each Scene contains exactly one source for
each declared variant. Comparable variants for a Scene/attribute share compatible
physical grid topology; PixelScope never index-zips incompatible grids or aligns
source images to manufacture a comparison.

## IQA attributes and numerical semantics

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

Schema v2 retains mandatory server-authored W/S1/S2/count/valid grid sufficient
statistics. The canonical Scene absolute mean is `ΣS1/ΣW`; the server's weighting is
not reconstructed locally.

Small server-authored summary metadata contains deterministic projections of the
normative accumulators. Projection mismatch beyond the schema tolerance is corrupt;
there is no dual numerical authority.

Dataset absolute summary exposes both pooled-weighted and equal-Scene reductions.
**The owner-selected default absolute Dataset Overview is `pooled_weighted_mean`.**

Reference-dependent local comparison uses target/reference pair-valid grid
intersection. Power attributes retain two labeled modes:

1. ratio of pair-valid aggregate weighted means;
2. arithmetic mean of pair-valid grid log-ratios.

Signed attributes use pair-valid weighted target mean minus pair-valid weighted
reference mean.

For relative Dataset Overview, **the owner-selected default is arithmetic mean of the
selected comparison value computed independently for each valid Scene**. Thus the
relative Overview is the equal-Scene reduction of Scene Trend. Any future pooled
relative mode must be separately named.

## Remote analysis domain and exact spatial convention

4K-class RGB input is processed in an approximately 2K remote analysis domain.
Structural maps, attribute maps, weights, and grids carry explicit geometry.

The continuous pixel-edge coordinate convention, half-open cells/valid rectangles,
row-major source→analysis affine, and continuous inverse mapping established by the
merged schema-v1 contract remain the geometry baseline unless a future schema
explicitly changes them.

A fixed resize factor is never assumed.

## Remote input and deterministic submission baseline

The merged v1 remote input policy remains the current submission baseline until P5-C
explicitly extends it: PNG/JPG/JPEG/BMP families only, no silent RAW conversion.

Current Pair remains bound to deterministic underlying Current Comparison Page source
order rather than Primary/Active/view order. Folder pairing remains deterministic and
explicit before submit. A future N-way request shape must preserve ordered explicit
Scene manifests rather than relying on server re-sorting.

## Result and bandwidth strategy — purpose-based artifacts

Schema v2 removes the old numerical rule that compact Scene data is only an
inspected-Scene lazy Tier.

The result categories are:

1. **Summary metadata** — small open-time absolute Dataset/Scene summaries and
   provenance.
2. **Grid measurement artifacts** — compact per-source grid W/S1/S2/count/valid used
   for exact local relative calculations and spatial views.
3. **Optional detail artifacts** — large per-pixel 2K/debug/structural maps.

Loading policy is separate from schema semantics. PixelScope may read grids by Scene,
bounded batch, background request, or bounded cache. All policies remain bounded,
stale-safe, and non-blocking for network storage.

The v2 result keeps `kind = pixelscope-iqa-result`, targets `schema_version = 2`, uses
safe relative artifacts/data-only NumPy, and retains immutable publication.

Schema v1 remains explicit read-only compatibility for historical two-source results;
there is no synthetic v1→v2 upgrade that invents absolute measurements.

## Shared storage and HTTP direction

Client and GPU server may see the same SMB/network storage through different physical
paths. P5 uses a logical storage-root ID + relative path instead of embedding local
Windows or server Linux paths in the API.

The existing external server has a blocking HTTP interface. P5 targets an async
submit/status/result/cancel job API with polling as the initial progress mechanism.
WebSocket progress is optional future work.

## PARTIAL/failure direction

The owner has already fixed the central policy: **durable PARTIAL results are allowed
and successful Scene work must be preservable when another Scene fails**.

Schema v2 carries that decision forward. P5-C still owns detailed request rejection,
per-Scene failure records, missing-variant rules, exact PARTIAL terminal identity,
required artifacts, no-success behavior, and cancel/publication races.

Unevaluable source cohorts, including incompatible original dimensions, are rejected
or excluded by server evaluation; PixelScope does not align/resize them locally.

## UX direction

P5 adds one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

- large batch references are not eagerly Registered/Selected/decoded;
- jobs do not forcibly replace the current local workspace;
- passive results do not mutate Selected;
- summary metadata provides immediate absolute Overview/Scene Trend;
- IQA Reference uses `variant_id` and remains independent from Primary;
- relative views are locally derived from accepted source measurements;
- required grid I/O/calculation runs asynchronously and may expose Loading/Calculating;
- explicit Inspect loads only chosen Scene sources through canonical local authority;
- temporary P4-A Picks block conflicting Inspect entry;
- transient Return-to-previous-workspace never overwrites newer non-IQA intent;
- result navigation drills down dataset → attribute → Scene → block.

# P5 execution sequence

Current sequence with the schema correction is:

`P5-0 → P5-A(v1) → P5-A2(schema-v2 migration) → P5-B → P5-C → P5-D → P5-E → P5-F → P5 Complete`

## P5-0 — P4 Closure & P5 Program Setup — Complete

Docs-only orchestration slice that closed P4 and established the original P5 contracts.

## P5-A — Contract Fixtures & IQA Domain / schema v1 — Complete

P5-A merged as PR #37 at
`fceb16f6e43c48ec65fbf7ebbcc103b56716b686`.

It delivered:

- Qt-free versioned Result/Scene/Source/Attribute/comparison models;
- schema-v1 manifest/summary/compact-scene parser;
- deterministic production-shaped fixtures including an N-source structural case;
- W/S1/S2/count/valid recomposition and two pairwise power modes;
- exact source→analysis geometry mapping;
- bounded safe artifact parsing/corruption handling.

P5-A is now the **historical executable schema-v1 baseline**, not the current
numerical target.

## P5-A2 — Schema v2 source-measurement migration — Active

P5-A2 exists because P5-B review exposed that pairwise server summaries do not scale
cleanly to N-way Reference switching.

### Stage 1 — durable contract revision / PR #39

PR #39 freezes:

- `variant_id` vs `source_id` identity;
- Scene-context-scoped absolute source measurements;
- complete-result variant cardinality and grid correspondence;
- server W/S1/S2/count/valid numerical authority;
- canonical Scene absolute reduction;
- pooled + equal-Scene absolute dataset summaries;
- default absolute Overview = pooled weighted mean;
- local target/reference power/signed comparisons;
- default relative Overview = arithmetic mean of valid Scene comparisons;
- v1 read-only compatibility;
- PARTIAL direction carry-forward;
- separation of schema semantics from grid loading/cache policy.

### Stage 2 — focused executable-v2 migration

After PR #39 merges, a separate focused implementation PR must update the domain,
fixture, reader/writer shape, and golden tests before P5-B resumes. It must freeze and
test concrete field/array placement, dtype/shape rules, v2 safety ceilings,
`measurement_context_id` construction, summary consistency, grid correspondence,
N-way identity, and v1 compatibility dispatch.

P5-B must not implement these parser/schema decisions itself.

## P5-B — IQA Workspace & Local Result Exploration — Paused / schema-dependent

PR #38 contains work in progress but is intentionally paused until **P5-A2 Stage 2
executable v2** is merged to `main`.

After that baseline exists, P5-B rebases and is revised to:

- use the canonical Open IQA Result path against v2;
- support N-way `variant_id` Reference selection;
- show absolute summary-based initial Overview and Scene Trend;
- default absolute Dataset Overview to `pooled_weighted_mean`;
- derive reference-dependent comparisons locally;
- default relative Overview to arithmetic mean of valid Scene comparison values;
- keep grid I/O/calculation off the UI thread with stale-result rejection;
- preserve passive Files/Selected/native-analysis state;
- preserve lifecycle/close-recreate safety.

## P5-C — Submission & Shared Storage — Planned

P5-C must not start until remaining owner/orchestrator gates are frozen.

**Gate C1 — machine-local logical storage-root configuration ownership**

C1 remains intentionally deferred. Choose whether `storage_root_id → client/UNC path`
is typed `ApplicationSettings` with explicit migration or another already-authoritative
machine-local configuration mechanism. Result artifacts and Session cannot own this
mapping.

**Gate C2 — PARTIAL allowed; detailed failure/terminal policy pending**

The central direction is fixed: durable PARTIAL results are allowed and successful
Scene outputs are preservable. P5-C must still freeze request rejection, per-Scene
failure records, missing variants, exact PARTIAL API/terminal identity, required
artifacts, no-success behavior, and cancel/completion/publication races.

After gates close, P5-C owns safe staging, deterministic submission, explicit Scene
manifests, HTTP job lifecycle, polling Jobs UI, and handoff into P5-B's canonical Open
Result path.

GPU server implementation remains outside this repository.

## P5-D — Viewer-linked Scene Inspection — Planned

Connect IQA anomalies to source locations:

- explicit Inspect and Pick-state guard;
- canonical loading of only inspected Scene sources;
- transient return snapshot with stale-intent invalidation;
- IQA Reference independent from Primary;
- linked Scene navigation;
- exact analysis-grid → source → viewer mapping;
- vector/block overlay and block inspector from v2 absolute/relative grids;
- safe interaction with Difference/Gain/ROI/Line.

## P5-E — Historical Result Workflow — Planned

Make completed results reusable by extending, not replacing, P5-B's canonical result
open path:

- bounded Recent IQA Results;
- production logical-root reopen;
- immutable result/source-hash identity;
- result-only mode when source images are unavailable;
- source/hash mismatch diagnostics;
- provenance display;
- explicit v1 read-only historical result handling where applicable.

P5 does **not** modify Session v1. A future IQA reference inside Session requires a
new explicit Session schema/version decision. P6 remains responsible for auth/SSO,
credentials, permission, audit administration, and access policy.

## P5-F — Integration & Performance Hardening — Planned

Validate the composed workflow against the real server and realistic datasets:

- real schema-v2 API/result compatibility plus v1 read-only history;
- bounded grid loading/cache behavior;
- SMB/network bandwidth characterization;
- local reference-switch calculation latency;
- current-pair and large-folder/N-way stress;
- cancellation/failure/missing artifacts;
- stale callback and application close/recreate safety;
- proof batch membership does not become local source/residency/preload authority;
- optional detail characterization;
- P5 closure documentation.

No fixed wall-clock latency is a correctness merge gate. Correctness gates are stable
versioned identity/math/geometry, bounded ownership, no duplicate work, stale-result
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
