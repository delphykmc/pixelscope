# Remote IQA contract

Status: P5 durable contract — executable schema-v2 + P5-C/P5-D merged + P5-E historical workflow active
Owner: PixelScope P5 program + external IQA server contract
Established: P5-0; numerical ownership revised by PR #39; P5-C transport/storage/failure contract frozen in PR #42; P5-D native inspection frozen in PR #43

This document defines the stable product/architecture boundary for PixelScope P5.
The external GPU IQA implementation lives in a separate repository. PixelScope
consumes a versioned job/result contract and does not reimplement the server's signal
extraction models.

**The current P5 numerical/result target is schema v2 in
[`REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).** The merged P5-A/schema-v1 contract
in [`REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md) remains the historical executable
baseline and explicit read-only compatibility definition. It must not be silently
reinterpreted as v2.

P5-E historical reopen is specialized in
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

The current ownership principle is:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

## 1. Product goal

P5 lets a user:

1. inspect images quickly with existing local PixelScope comparison tools;
2. submit a current pair or a large deterministic evaluation to the GPU IQA service;
3. continue normal PixelScope work while a remote job runs;
4. reopen durable historical results instead of rerunning the GPU job;
5. explore `dataset → attribute → scene → spatial block`;
6. switch IQA Reference across N-way comparison variants;
7. explicitly inspect selected IQA scenes in the existing viewer.

## 2. Existing PixelScope authority remains unchanged

P5 inherits the sole local image/runtime hierarchy:

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

`Analysis Working Set = Current Comparison Page` remains authoritative for existing
Statistics, Histogram, Line Profile, Difference, source protection, and page loading.

Remote IQA batch/result/history membership is feature-local and must not itself:

- register/decode all batch inputs;
- own source residency/protection or preload;
- change source generations;
- redefine Difference/cache identity;
- redefine Display Gain/native analysis semantics;
- persist remote arrays/running jobs into Session v1.

P5 does not change Session v1. Any future IQA-in-Session persistence requires a new
explicit Session schema/version decision.

## 3. Scene-based remote authority and N-way identity

The current remote result model is:

```text
IQA Job / Result
    ↓
ordered variants[]                 # stable comparison-group identity
    ↓
Scene / measurement context
    ├─ exactly one source per variant for every published successful Scene
    ├─ representative image / structural context
    ├─ common Edge Map
    ├─ common Texture Gate
    └─ per-source absolute attribute measurements
          ↓
     PixelScope-derived reference comparisons
```

Schema v2 distinguishes:

- `variant_id`: one comparison group/configuration across Scenes;
- `source_id`: one concrete image;
- `scene_id`: one evaluation Scene;
- `measurement_context_id`: the Scene evaluation context in which the weighted
  source measurement is valid.

Reference selection addresses `variant_id`; source inspection addresses concrete
`source_id` values.

An absolute source measurement is **reference-independent inside its published Scene
context**, not globally context-free. The common Edge Map/Texture Gate and effective
weighting can depend on the representative/cohort. A weighted measurement cannot be
transplanted across incompatible Scene/job/cohort contexts merely because a source
SHA matches. Server caches may reuse lower-level features only where mathematically
valid.

For COMPLETE and for each successful Scene inside PARTIAL, the published Scene remains
a full schema-v2 Scene with exactly one source for each declared variant. P5-C does
not serialize an incomplete successful Scene with a missing variant. A Scene that
cannot produce the complete comparable cohort is represented as a failed/cancelled
`scene_outcome` rather than an imputed or locally repaired Scene.

## 4. Ten IQA attributes

| Attribute | Quality direction | Current default block |
|---|---|---:|
| Luma noise | lower is better | 32×32 px |
| Luma detail | higher is better | 32×32 px |
| Chroma noise | lower is better | 32×32 px |
| Chroma detail | higher is better | 32×32 px |
| Edge strength | higher is better | 32×32 px |
| Luma contrast | higher is better | 128×128 px |
| Luma bias | neutral / signed | 128×128 px |
| Chroma contrast | higher is better | 128×128 px |
| Chroma bias | neutral / signed | 128×128 px |
| Colorfulness | higher is better | 128×128 px |

Block sizes are server metadata, not PixelScope constants. Attribute metadata carries
stable ID/name, value kind, comparison operator, quality direction, units, block/grid
geometry, weighting provenance, and required stabilization metadata.

Power attributes keep raw engineering orientation separate from user-facing quality
interpretation. Signed bias attributes remain signed/neutral and are not converted to
power-ratio dB.

## 5. Remote analysis domain and geometry

The GPU service operates on RGB-family encoded image inputs. P5-C submission accepts
PNG/JPG/JPEG/BMP only. Local RAW support does not imply a silent remote RAW conversion
path.

All sources in a comparable Scene must have equal original dimensions. Unevaluable
cohorts are rejected/excluded by server evaluation under the applicable failure
policy; PixelScope does not align or resize them to manufacture IQA comparisons.

For performance, 4K-class inputs are normally downscaled to approximately 2K before
structural/attribute maps and grid statistics are created.

The result carries exact original/analysis geometry, source→analysis transform, valid
analysis rectangle, grid origin/dimensions, block size, and border-discard metadata.
PixelScope never assumes a fixed scale.

For each comparable `Scene × attribute`, participating variants must have compatible
physical grid correspondence: rows/columns, block size, origin/indexing, valid region,
and analysis geometry must identify the same cell regions. PixelScope never zips
mismatched grids by index.

The continuous pixel-edge/half-open coordinate convention established by schema v1
remains the geometry baseline unless a future schema explicitly changes it.

## 6. Measurement statistics and recomposition

The server uses weighted mean and weighted population standard deviation. Noise may be
weighted toward flat regions, detail toward texture, and Edge strength toward edges;
exact weighting/gating is server-profile and Scene-context provenance.

For every `Scene × source × attribute × grid`, schema v2 retains mandatory
W/S1/S2/count/valid sufficient statistics:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid_mask
```

The canonical Scene absolute mean is:

```text
Σ weighted_sum / Σ weight_sum
```

and the corresponding population variance/std is recomposed from W/S1/S2. This is the
normative source-local Scene statistic; an arithmetic mean of grid means is not
another unnamed `mean`.

The server also publishes small Scene and dataset summary projections so normal
result open does not scan every grid artifact. W/S1/S2/count/valid plus the normative
formulas remain the numerical authority; serialized mean/std projections must agree
within the schema-v2 tolerance or the artifact is corrupt.

For dataset absolute summaries, schema v2 publishes both:

- pooled weighted mean/std across Scene measurements;
- equal-Scene mean/std across valid canonical Scene means.

**The default absolute Dataset Overview is the pooled weighted mean.**

## 7. Local reference-dependent comparison

Schema v2 does not require server-authored pairwise tables as normal numerical
authority. PixelScope selects a reference variant and derives each target/reference
comparison from immutable server measurements.

Pair-valid support is the intersection of target/reference valid cells on a previously
validated common grid topology.

Power attributes keep two explicit comparison modes:

1. ratio of pair-valid aggregate weighted means;
2. arithmetic mean of finite pair-valid per-grid log ratios.

Signed attributes use pair-valid weighted target mean minus pair-valid weighted
reference mean.

For relative Dataset Overview, the owner-selected default is:

```text
compute the selected comparison independently per valid Scene
    ↓
arithmetic mean of valid Scene comparison values
```

This applies to both power modes and signed deltas. A future pooled-across-Scenes
relative mode must be explicitly named; it is not silently substituted for the
default.

Optional server pairwise values may exist as diagnostics/verification, but are marked
derived and do not become a second user-facing numerical authority.

## 8. Durable result artifact categories and historical retention

P5 avoids eager full-map transfer, but schema v2 separates **artifact purpose** from
client loading policy:

1. **Summary metadata** — small open-time manifest plus absolute Dataset/Scene
   summaries and provenance.
2. **Grid measurement artifacts** — mandatory compact W/S1/S2/count/valid analytical
   source for local reference comparisons and spatial grids.
3. **Optional detail artifacts** — larger per-pixel 2K attributes, common Edge Map,
   Texture Gate, representative image, and debugging artifacts.

Conceptual layout remains:

```text
result/<job-id>/
    manifest.json
    summary.npz
    scenes/
        scene_000001.npz
        ...
    detail/
        ... optional ...
```

Grid artifacts are not numerically defined as "inspected-Scene-only lazy Tier 2".
PixelScope may load them per Scene, bounded batch, background request, or bounded cache
according to measured runtime needs. The policy remains bounded, stale-safe, and
non-blocking for network storage.

Published results are immutable historical engineering artifacts. P5-E records only a
small locator plus observed `result_id + schema_version`; it does not copy the Result,
create a second artifact format, or add a whole-result digest. Ordinary clients expect
published Results to persist until explicit/administrative deletion. Authentication,
identity, permission, and administration remain P6.

## 9. Shared storage abstraction — P5-C frozen

Client and GPU server may mount the same SMB/network storage at different paths. The
API uses logical root + relative path, never machine-local paths as portable identity:

```text
storage_root_id = iqadata
relative_path = project42/A/0001.png

client: iqadata → G:\IQA
server: iqadata → /home/data/IQA
```

P5-C freezes the machine-local ownership in typed `ApplicationSettings` schema v6:

```text
RemoteIqaSettings
    server_base_url
    storage_roots[] {
        storage_root_id
        client_path
    }
    staging_root_id
```

`storage_root_id` is the portable identity shared by client/server. `client_path` is
machine-local and is never serialized into the job request or result artifact. Server
physical paths and credentials are not persisted by PixelScope. Session v1 does not
own these mappings.

Existing sources under a configured root are represented by the most-specific matching
logical root plus portable POSIX relative path. Sources outside configured roots may be
staged under the configured staging root using content-addressed SHA-256 identity.
Staging uses independently named same-directory `.part` files, resolved containment
before mutation, atomic final publication, and SHA-256 winner/reuse verification.
Cross-process concurrent publication and source/result symlink or junction escapes are
covered by the P5-C implementation and regression suite without changing the logical
identity contract above.

P5-E reuses the same abstraction for historical Results. A production historical
locator is `storage_root_id + relative_path`; current machine mapping is resolved only
when the user reopens the entry. Jobs history preserves the server-published logical
Result reference instead of persisting the currently mapped drive/UNC path.

## 10. Submission pairing and PARTIAL contract — P5-C frozen

Request/result/Scene-manifest identity remains N-way-capable, but the **initial P5-C
user-facing submission workflow is exactly two variants**:

- Current Pair submits the A/B pair of underlying Current Comparison Page documents;
- A/B identity follows deterministic underlying page/source order and is independent
  from Primary, Active, view reorder, Display Gain, Difference, or Split presentation;
- Folder Pair uses immediate eligible files only, no recursion, no symlinks, Unicode
  NFC lexical ordering, equal eligible counts, and pair-by-index ordering;
- each submitted pair must have equal original dimensions;
- request Scene IDs are deterministic `scene_000000...` and each Scene serializes A
  then B;
- arbitrary three-or-more-variant submission UI is deferred to a later explicit
  owner decision;
- P5-B remains capable of opening externally produced N-way schema-v2 results.

Client-known preflight errors block the request before job creation. Server-side
per-Scene evaluation failures are represented by the terminal result taxonomy below.
The client does not resize/align or synthesize a missing variant.

Durable PARTIAL results are executable schema-v2 results with these rules:

- `publication_state = "partial"`;
- `scene_outcomes[]` covers **every requested Scene in original request order**;
- each outcome has unique `scene_id` and status `succeeded`, `failed`, or `cancelled`;
- `succeeded` outcomes contain no error diagnostics;
- `failed`/`cancelled` outcomes require bounded `error {code, message}` and may carry
  optional boolean `retryable`;
- at least one Scene must succeed and at least one Scene must fail/cancel;
- `scenes[]` contains **only** fully published successful Scenes, in the same order
  as the successful `scene_outcomes`;
- every published successful Scene still satisfies the normal complete-Scene v2
  numerical/cardinality/geometry invariants;
- zero-success jobs are not PARTIAL; they terminate `failed` or `cancelled` and have
  no published result reference;
- all-success jobs are `succeeded` with `publication_state = "complete"`.

For COMPLETE and PARTIAL, `manifest.json` remains the immutable publication commit
marker and summary/grid artifacts cover only the published successful `scenes[]`.
P5-E history/provenance does not alter publication state or synthesize missing Scenes.

## 11. Job API and retry contract — P5-C frozen

P5-C uses the following polling REST boundary:

```text
POST /v1/iqa/jobs                  → job_id + non-terminal state
GET  /v1/iqa/jobs/{job_id}         → progress/state
GET  /v1/iqa/jobs/{job_id}/result  → logical result reference
POST /v1/iqa/jobs/{job_id}/cancel  → server-owned resulting state
```

States are:

```text
queued
preparing
extracting
aggregating
writing
succeeded
partial
failed
cancelled
```

Terminal states are `succeeded`, `partial`, `failed`, and `cancelled`. Only
`succeeded` and `partial` may resolve an immutable result reference. The result
reference contains `job_id`, `storage_root_id`, portable `relative_path`,
`schema_version = 2`, and matching `publication_state` (`complete` for succeeded,
`partial` for partial).

Polling is the initial default; WebSocket is not required. Job completion never
automatically opens or replaces the current IQA result. The user explicitly chooses
`Open Result`, which resolves the logical result reference through current machine-local
settings and delegates to the existing P5-B canonical result loader/controller.

Retry semantics are asymmetric by operation:

- create `POST /jobs` is **never automatically retried** because timeout after server
  acceptance is an ambiguous create;
- status/result/cancel operations are idempotent/safe only where their endpoint
  semantics allow it;
- after terminal `succeeded`/`partial`, initial `GET /result` is attempted once by the
  existing lifecycle; transient result-reference failure is retried only for that
  idempotent GET with bounded 1s/2s/4s/8s backoff;
- retry exhaustion leaves the terminal job visible with an explicit error; it never
  converts the job to another terminal state and never resubmits the job.

Client diagnostics classify configuration, connection, timeout, HTTP, protocol, and
storage-resolution failures so the Jobs UI can present bounded actionable errors.

The exact production server implementation remains external. PR #42 includes a
real-socket localhost `ThreadingHTTPServer` fault harness only to exercise this client
contract before a GPU server is available; that debug server is not production
server architecture.

## 12. UX contract

P5 uses one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
    ├─ Dataset/Scene exploration
    ├─ P5-D Inspect / Return / spatial inspection
    └─ P5-E Provenance
```

Setup owns Current Pair and deterministic Folder Pair preparation/submission. Jobs owns
locally tracked durable job state, Cancel, and explicit Open Result. Results embeds the
existing P5-B result workspace rather than creating a second result parser/controller.

Native OS file/folder pickers may remain modal; pairing, jobs, result exploration,
historical reopen, and Scene inspection remain non-modal. A job reaching
COMPLETE/PARTIAL does not auto-open Results.

P5-E adds **File > Open Recent IQA Results** with bounded max-10 MRU entries and Clear.
It is independent from P4-C Recent Images/Folders/Sessions. Missing/offline/remapped
historical entries remain until explicit Remove/Clear.

Result exploration follows:

```text
Job / dataset
    ↓
absolute/relative attribute overview
    ↓
attribute Scene Trend / outliers
    ↓
Scene
    ↓
spatial grid comparison
    ↓
block inspector
```

Summary metadata supports immediate absolute Overview/Scene Trend. Reference-dependent
views may load compact grid measurements asynchronously and show Loading/Calculating
state.

Passive result browsing, Recent reopen, and Provenance never change Selected. Explicit
Inspect loads only the chosen Scene sources through the canonical local registration/
selection path. IQA Reference is independent from Primary.

P5 blocks conflicting Inspect while a P4-A temporary Pick baseline is active.
Return-to-previous-workspace remains transient and must not overwrite newer non-IQA
workspace intent.

Debug-only P5-C tools are gated by `PIXELSCOPE_REMOTE_IQA_DEBUG` and are not release
workflow authority. Request Inspector runs the production request-builder path but
stops before POST. Replay JSON injects bounded logical terminal job/result references
without HTTP and still requires explicit Open Result. The localhost fault server uses
real HTTP solely for client-contract validation.

## 13. Historical Result ownership — P5-E

All historical open paths converge on the canonical P5-B result loader:

```text
File > Open IQA Result...
Jobs > Open Result
File > Open Recent IQA Results
        ↓
P5-E locator + expected historical identity context
        ↓
P5-D new-result teardown
        ↓
P5-B canonical loader / P5-A2-v1 dispatch
        ↓
existing Results workspace
```

Historical locator types are:

- portable logical Result locator: `storage_root_id + relative_path`;
- machine-local absolute locator: manual/out-of-root and explicit schema-v1 fallback.

Recent IQA metadata is separate observer persistence under `recent/iqa_results`, payload
version 1, max 10, MRU, locator-deduplicated. It is not `ApplicationSettings`, does not
increment settings schema v6, and is not Session v1.

A successful open records observed `result_id + schema_version`. Recent reopen compares
the observed identity after the canonical reader succeeds but before Results
`set_model()`. Mismatch rejects the reopen, preserves the last valid current Result, and
keeps the old history entry unless the user removes it.

No whole-result hash is added. Structural/numerical integrity remains the canonical
artifact reader's responsibility.

Result-only browsing deliberately does not stat/hash/decode all native sources.
Source existence/dimension/SHA/decode/containment checks remain lazy P5-D Inspect
authority. Therefore missing sources can disable Inspect while the immutable server
Result stays browseable.

P5-E Provenance displays published v2 Result/Scene/source provenance and current native
inspection state without recomputing IQA or decoding source pixels. Schema v1 remains
explicit historical/read-only with no invented v2 metadata.

## 14. Open Result ownership and current P5 sequence

P5-B / PR #38 owns the one canonical Result parser/controller/workspace. P5-C / PR #42
extends the same IQA dock with Setup/Jobs. P5-D / PR #43 composes verified explicit
native Inspect/Return on top. P5-E / Draft PR #44 extends the same open path with bounded
historical discovery and Provenance.

Current sequence is:

```text
P5-A/schema v1 merged (#37)
    ↓
P5-A2 durable + executable schema v2 merged (#39/#40)
    ↓
P5-B local result workspace merged (#38)
    ↓
P5-C submission/shared-storage client merged (#42)
    ↓
P5-D viewer-linked Scene inspection merged (#43)
    ↓
P5-E historical Result workflow active (Draft #44)
    ↓
P5-F real-server/performance hardening planned
```

If original images disappear, server result summaries and measurement artifacts remain
usable for result-only exploration while source-linked inspection/overlay may be
unavailable.

## 15. Executable compatibility and test harness ownership

P5-A/PR #37 remains the historical schema-v1 executable baseline. P5-A2 / PR #39 and
PR #40 define and implement the canonical schema-v2 domain, manifest/summary/grid
reader, deterministic context identity, numerical checks, safety ceilings, and
explicit v1 read-only dispatch.

P5-C extends that executable v2 reader with PARTIAL `scene_outcomes`; it does not
create a second numerical parser. Deterministic P5-C debug result generation reuses
the canonical v2 fixture writer and validates the generated artifact through the
canonical result loader before publishing replay metadata.

P5-D and P5-E consume those readers. Neither defines another numerical parser.
No silent v1→v2 numerical upgrade is allowed.

## 16. Explicit P5 boundaries

P5 does not own:

- external GPU model implementation/training;
- login/SSO/token/permission/admin lifecycle (P6);
- arbitrary server retention administration;
- local RAW demosaic/WB/CCM/tone-map conversion for remote submission;
- source-residency/preload redesign;
- Difference numerical redesign;
- Saved ROI/Overlay deferred from P4;
- packaging/signing/update strategy (P7).

P5 may request new versioned server interfaces/result writers, implemented in the
external IQA server repository.
