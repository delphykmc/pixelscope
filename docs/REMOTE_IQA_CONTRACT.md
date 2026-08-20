# Remote IQA contract

Status: P5 planning contract — schema-v2 numerical revision active
Owner: PixelScope P5 program + external IQA server contract
Established: P5-0; numerical ownership revised by PR #39

This document defines the stable product/architecture boundary for PixelScope P5.
The external GPU IQA implementation lives in a separate repository. PixelScope
consumes a versioned job/result contract and does not reimplement the server's signal
extraction models.

**The current P5 numerical/result target is schema v2 in
[`REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).** The merged P5-A/schema-v1 contract
in [`REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md) remains the historical executable
baseline and explicit read-only compatibility definition. It must not be silently
reinterpreted as v2.

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

Remote IQA batch/result membership is feature-local and must not itself:

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
    ├─ exactly one source per variant for normal complete results
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

For a normal non-PARTIAL complete result, each Scene contains exactly one source for
each declared variant, with no duplicate variant binding. Missing-variant semantics
belong to the detailed PARTIAL contract.

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

The GPU service operates on RGB-family encoded image inputs. The merged v1 input
eligibility rules remain the current submission baseline until a later transport
contract explicitly revises them; local RAW support does not imply a silent remote
RAW conversion path.

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

## 8. Durable result artifact categories

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

Published results are immutable historical engineering artifacts. Ordinary clients
expect them to persist until explicit/administrative deletion. Authentication,
identity, permission, and administration remain P6.

## 9. Shared storage abstraction

Client and GPU server may mount the same SMB/network storage at different paths. The
API uses logical root + relative path, never machine-local paths as portable identity:

```text
storage_root_id = iqadata
relative_path = project42/A/0001.png

client: iqadata → G:\IQA
server: iqadata → /home/data/IQA
```

Local inputs may be staged safely; partial copies must not become visible as complete
server inputs. Content-addressed SHA-256 reuse is preferred where practical.

The machine-local configuration owner for logical-root→client-path mapping remains an
explicit P5-C decision gate. Result artifacts and Session cannot own it.

## 10. Submission pairing and failure direction

The current submission baseline supports Current Pair from an already-open
deterministic two-source page and deterministic folder-based batch formation. P5-C may
extend the request shape for N-way variants, but must preserve explicit ordered Scene
manifests and must not make server re-sorting or local Primary/Active/view reorder
identity authority.

Large batch references do not become Files/Selected/decoded source ownership.

The owner-approved failure direction is already fixed:

> **Durable PARTIAL results are allowed and successful Scene work must be
> preservable when another Scene fails.**

P5-C still must freeze request-level rejection, per-Scene failure records, exact
PARTIAL terminal identity, missing-variant rules, required artifacts, no-success
behavior, and cancel/completion/publication races.

## 11. Job API target

The existing service has a blocking HTTP interface. P5 targets a separable async job
adapter:

```text
POST /v1/iqa/jobs                  → job_id
GET  /v1/iqa/jobs/{job_id}         → progress/state
GET  /v1/iqa/jobs/{job_id}/result  → logical result reference
POST /v1/iqa/jobs/{job_id}/cancel
```

Polling is the initial default; WebSocket is not required. Typical 4K extraction is
about two seconds per source, so batch work is non-modal and cancellable. A result is
not historically openable until its immutable publication contract is complete for
the applicable COMPLETE/PARTIAL terminal state.

## 12. UX contract

P5 adds one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

Native OS file/folder pickers may remain modal; pairing, jobs, and result exploration
remain non-modal.

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

Passive result browsing never changes Selected. Explicit Inspect loads only the chosen
Scene sources through the canonical local registration/selection path. IQA Reference
is independent from Primary.

P5 blocks conflicting Inspect while a P4-A temporary Pick baseline is active.
Return-to-previous-workspace remains transient and must not overwrite newer non-IQA
workspace intent.

## 13. Open Result ownership and current P5 interruption

P5-B owns the one canonical `Open IQA Result...` controller/parser path; P5-E later
extends that same path with production logical-storage reopen, bounded Recent IQA
Results, provenance, source/hash diagnostics, and result-only mode.

However, P5-B schema-dependent implementation is currently **paused**. Sequence is:

```text
P5-A/schema v1 merged (#37)
    ↓
PR #39 schema-v2 contract merge
    ↓
focused executable-v2 domain/fixture/parser migration
    ↓
P5-B rebase/revision against executable v2
```

P5-B must not invent schema-v2 parser/field/safety semantics before that focused
migration lands.

If original images disappear, server result summaries and measurement artifacts remain
usable for result-only exploration while source-linked inspection/overlay may be
unavailable.

## 14. Fixture-first implementation and compatibility

P5-A/PR #37 at `fceb16f6e43c48ec65fbf7ebbcc103b56716b686` is the merged historical
schema-v1 executable baseline. Its deterministic fixture proves v1 math, geometry,
parser safety, publication, and N-source structural identity.

After PR #39 merges, a focused executable-v2 migration must update the Qt-free domain,
manifest/summary/grid parser, fixture writer, and golden numerical tests before P5-B
resumes. That migration must also implement:

- explicit v1 read-only compatibility dispatch;
- N-way `variant_id` identity and complete-result cardinality;
- `measurement_context_id` construction;
- cross-variant grid-correspondence validation;
- summary projection consistency validation;
- justified v2 safety ceilings and concrete field/dtype/shape rules.

No silent v1→v2 numerical upgrade is allowed.

## 15. Explicit P5 boundaries

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
