# Remote IQA schema v2 source-measurement specification

Status: Current P5 numerical target proposed for merge in PR #39
Owner: PixelScope P5 program + external IQA server contract
Historical executable baseline: P5-A / PR #37 / schema v1
Target schema identity: `kind = "pixelscope-iqa-result"`, `schema_version = 2`

This document defines the P5 schema-v2 numerical/result target that replaces the
pairwise-centered numerical ownership model of the merged P5-A schema-v1 baseline.
The governing principle is:

> **The server owns measurement. PixelScope owns reference-dependent comparison,
> aggregation views, and visualization.**

The GPU service remains authoritative for source decoding, IQA signal extraction,
Scene-context weighting/gating, validity, analysis/grid geometry, and sufficient
statistics. PixelScope does not run the IQA models and does not reconstruct weighting
from visualization maps. It consumes immutable server-authored source measurements and
locally derives the comparison requested by the user.

The durable model is N-way. A/B remains a convenient two-variant presentation, but
the result contract must support A/B/C/D-style comparison groups and arbitrary IQA
Reference switching without requiring the server to serialize every pairwise
combination.

## 1. Relationship to schema v1 and compatibility policy

`REMOTE_IQA_V1_SPEC.md` remains the historical normative record for the merged P5-A
schema-v1 implementation and fixtures. It is not rewritten by schema v2.

Schema v2 changes the active numerical ownership contract:

- server-authored pairwise comparison records are no longer the primary numerical
  source of truth;
- the durable source of truth is the server-authored measurement for each Scene
  source/variant;
- `variant_id` provides stable comparison-group identity across Scenes;
- small absolute Scene/dataset summaries provide the fast open-time path;
- absolute grid sufficient statistics are the common analytical input for local
  relative statistics and spatial visualization;
- the old rule that compact Scene grids are an inspected-Scene-only lazy tier is not
  numerical schema semantics;
- actual grid loading, batching, preload, and caching are bounded client performance
  policy.

Compatibility is frozen as follows:

1. schema v2 becomes the current/default writer and result model after the executable
   v2 migration lands;
2. schema v1 remains explicit **read-only compatibility** for historical two-source
   results and repository fixtures;
3. PixelScope must not silently "upgrade" v1 by inventing v2 absolute source
   measurements from pairwise v1 summaries;
4. v1 UI capability may remain limited to information actually present in v1;
5. new production writers and new golden fixtures target v2 after the migration
   slice;
6. unsupported future versions are rejected without best-effort guessing.

The active P5-B branch is schema-dependent and must remain paused until the executable
v2 domain/fixture/parser migration has landed on `main`, then rebase and adapt to this
contract.

## 2. Scene evaluation context: what "absolute" means

An **absolute source measurement** is reference-independent **inside one published
Scene evaluation context**. It is not necessarily context-free or globally reusable.

A Scene owns common structural context. The representative image, PiDiNet Edge Map,
Texture Gate, preprocessing profile, and effective weighting/gating may depend on the
Scene cohort. Therefore the same source image evaluated in another Scene/job/cohort
may legitimately receive a different weighted published measurement even though its
file hash is unchanged.

Schema v2 therefore requires a stable opaque `measurement_context_id` (or equivalent
fingerprint) for each published Scene evaluation context. Its provenance must bind at
least the information capable of changing a published weighted measurement:

- Scene/cohort identity and ordered variant/source membership;
- source content identities/hashes;
- representative-image identity or deterministic representative derivation policy;
- analysis preprocessing/profile version;
- IQA model/attribute version;
- weighting/gating configuration and structural-model provenance;
- geometry/profile metadata required to interpret the measurement.

The exact fingerprint encoding is a writer implementation detail, but incompatible
contexts must not share an identity.

A server may cache and reuse lower-level source features when that reuse is
mathematically valid. It must **not** transplant a published weighted source
measurement across incompatible Scene contexts merely because `source_id`, path, or
SHA-256 matches.

## 3. Result, variant, Scene, and source identity

Schema v2 separates comparison-group identity from concrete-image identity.

- `variant_id` identifies one comparison group/configuration across the result.
- `source_id` identifies one concrete image in the result.
- `scene_id` identifies one evaluation Scene.
- every Scene source records both `variant_id` and `source_id`;
- top-level ordered `variants[]` provides stable reference/display ordering;
- display label/name is metadata and is not the durable `variant_id`;
- source paths/hashes remain historical source identity, not directly openable
  machine-local paths.

Conceptually:

```text
Result variants: A, B, C, D

Scene 0001 / context X
├─ source A-0001 -> variant A
├─ source B-0001 -> variant B
├─ source C-0001 -> variant C
└─ source D-0001 -> variant D

Scene 0002 / context Y
├─ source A-0002 -> variant A
├─ source B-0002 -> variant B
├─ source C-0002 -> variant C
└─ source D-0002 -> variant D
```

### 3.1 Complete-result structural invariants

For a normal non-PARTIAL complete result:

- top-level `variant_id` values are unique and stable;
- `source_id` values are unique concrete-image identities within the result;
- every published Scene contains **exactly one source for every declared variant**;
- one Scene cannot bind two concrete sources to the same `variant_id`;
- reference selection of a `variant_id` therefore resolves to exactly one source in
  that Scene;
- all variants in a Scene have equal original dimensions;
- PixelScope never resizes, aligns, or imputes incompatible source images to create a
  comparison.

Missing variants in a PARTIAL result are governed by the later detailed PARTIAL
contract. They are not permitted as an ambiguous shape for a normal complete result.

## 4. Server numerical authority

For each valid `Scene × source × attribute`, the GPU server owns:

1. source decoding and analysis-domain preparation;
2. attribute signal extraction;
3. attribute-specific weighting/gating;
4. source/grid validity decisions;
5. analysis and grid geometry;
6. weighted sufficient statistics;
7. canonical source-local summary statistics;
8. measurement-context and model/profile provenance.

PixelScope must not derive IQA attributes from original image pixels and must not
reverse-engineer effective weights from Edge Map/Texture Gate visualization artifacts.

## 5. Required grid-level absolute measurements

For every `Scene × source × attribute × grid cell`, the server publishes the compact
sufficient statistics in the attribute's native numerical domain:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid_mask
```

The schema-v1 W/S1/S2/count/valid representation is retained because it preserves the
server's weighting while remaining sufficient for deterministic local reductions.

For one valid source-local cell:

```text
W  = weight_sum
S1 = weighted_sum
S2 = weighted_square_sum
mean = S1 / W
variance = max(0, S2/W - mean*mean)
std = sqrt(variance)
```

A cell is invalid if its explicit validity is false, count/weight is non-positive,
required values are non-finite, or its declared identity/geometry is invalid.
Unweighted attributes use unit weights rather than omitting the sufficient-statistic
fields.

The client may materialize `grid_mean = S1/W`. A writer may also serialize convenience
grid means, but W/S1/S2/count/valid remain normative.

## 6. Cross-variant grid correspondence is mandatory

Local `pair_valid[g]` is meaningful only when target cell `g` and reference cell `g`
represent the same physical analysis region.

For every comparable `Scene × attribute`, all participating variants must therefore
share one compatible grid topology/geometry:

- equal grid rows/columns and cell indexing;
- equal block width/height;
- equal grid origin;
- compatible/equal analysis valid rectangle;
- compatible source-to-analysis geometry so the same grid index denotes the same
  physical analysis region;
- the same attribute/grid identity required for indexwise comparison.

A writer may encode this as one shared Scene/attribute grid-geometry object or as
per-source metadata that validates equal. The representation is not important; the
**physical-cell correspondence invariant is normative**.

If this invariant is not satisfied, the server must reject/mark the cohort
incompatible according to the applicable failure policy. PixelScope must never zip
mismatched arrays by index or create an implicit alignment.

## 7. Canonical Scene-level absolute reduction

For a published `Scene × source × attribute`, the canonical absolute Scene scalar
uses all valid source-local grid cells and the sufficient statistics:

```text
scene_W  = Σ W[g]
scene_S1 = Σ S1[g]
scene_S2 = Σ S2[g]

weighted_mean = scene_S1 / scene_W
weighted_variance = max(0, scene_S2/scene_W - weighted_mean²)
weighted_std = sqrt(weighted_variance)
```

This `ΣS1/ΣW` weighted mean is the canonical Scene mean. The arithmetic mean of valid
`S1[g]/W[g]` cells is **not** another value called `mean`; if an equal-grid statistic
is useful later it must be separately named as a derived statistic.

## 8. Fast summary metadata and single numerical authority

Ordinary result open must not require opening every grid artifact. The server therefore
publishes small absolute summary metadata.

### 8.1 Scene-source-attribute summary

For every published `Scene × source/variant × attribute`, summary metadata includes at
least:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid
weighted_mean
weighted_std
```

W/S1/S2/count/valid and the formulas in this specification are the **normative
measurement authority**. Serialized `weighted_mean`/`weighted_std` are server-authored
fast projections, not a competing numerical authority.

A projection must agree with deterministic recomposition from its accumulators.
For finite floating values `a` and `b`, schema-v2 projection consistency uses:

```text
abs(a - b) <= max(1e-12, 1e-9 * max(abs(a), abs(b)))
```

Integer counts and boolean validity must agree exactly. A finite projection outside
this tolerance is invalid/corrupt; readers do not choose whichever value is more
convenient.

### 8.2 Dataset-variant-attribute summary

For every `variant × attribute`, the server publishes **both** of these inexpensive,
explicitly named absolute reductions across valid published Scenes.

#### A. Pooled measurement statistics

```text
pooled_W  = Σ scene_W
pooled_S1 = Σ scene_S1
pooled_S2 = Σ scene_S2

pooled_weighted_mean = pooled_S1 / pooled_W
pooled_weighted_variance = max(0, pooled_S2/pooled_W - pooled_weighted_mean²)
pooled_weighted_std = sqrt(pooled_weighted_variance)
```

**Owner-selected default for the absolute Dataset Overview: `pooled_weighted_mean`.**
This answers the database-wide measurement-support question and lets Scenes with more
effective valid weight contribute proportionally more.

#### B. Equal-Scene statistics

Let `m[s]` be the canonical valid Scene `weighted_mean` for the variant/attribute:

```text
scene_mean = arithmetic_mean(m[s])
scene_std  = population_std(m[s])
scene_count = number of valid Scene means
```

These are retained as secondary statistics because they answer a different question:
each Scene contributes one evaluation sample regardless of effective support.

Dataset pooled accumulators and their serialized projections must be consistent with
the contributing Scene accumulators using the same projection tolerance above.
`scene_mean`/`scene_std` must similarly agree with deterministic reduction of the
published valid Scene canonical means.

## 9. Removal of authoritative pairwise records

Schema v2 does not require the server to serialize every possible pairwise comparison.
For N variants, such output scales as O(N²) per attribute/mode and embeds a reference
choice into the stored result even though the source measurements are already
sufficient.

Pairwise values may be emitted as optional diagnostics or independent server-side
verification, but they are explicitly derived metadata. PixelScope must not require
such records for its normal v2 comparison path and must not treat them as a second
numerical authority.

## 10. Local reference-dependent comparison

PixelScope selects `reference_variant_id` and derives each target/reference comparison
locally from immutable server measurements.

For reference B in A/B/C/D:

```text
A vs B
C vs B
D vs B
```

Switching reference to C produces A/C, B/C, and D/C without another server evaluation.

### 10.1 Pair-valid support

For each Scene/attribute and a topology already proven compatible:

```text
pair_valid[g] = valid_target[g] AND valid_reference[g]
```

There is no union, imputation, resize, alignment, or client-generated weighting.

### 10.2 Power — ratio of weighted means

For the pair-valid set K:

```text
mean_target = Σ(K) S1_target[g] / Σ(K) W_target[g]
mean_ref    = Σ(K) S1_ref[g]    / Σ(K) W_ref[g]

raw_db = 10 * log10((mean_target + epsilon) / (mean_ref + epsilon))
```

`epsilon` remains mandatory server-authored AttributeSpec metadata in the same linear
power domain.

### 10.3 Power — mean of grid log-ratios

For each pair-valid grid cell:

```text
P_target[g] = S1_target[g] / W_target[g]
P_ref[g]    = S1_ref[g]    / W_ref[g]

grid_db[g] = 10 * log10((P_target[g] + epsilon) / (P_ref[g] + epsilon))
```

The Scene comparison is the **unweighted arithmetic mean** of finite valid `grid_db`
values, preserving the accepted schema-v1 meaning of this distinct comparison mode.
It must not be silently replaced by a weighted mean of dB cells.

### 10.4 Signed attributes

For signed attributes, use the same pair-valid cell intersection, recompute each
source's canonical weighted mean over that common support, then derive:

```text
signed_delta(target, reference) = mean_target - mean_reference
```

Signed values are not converted to power-ratio dB. Quality-direction presentation may
interpret a derived value, but it does not mutate the stored absolute measurement.

## 11. Dataset relative Overview default

Scene Trend retains the Scene axis. For each valid Scene, PixelScope first computes
the selected target/reference comparison using the selected comparison mode exactly as
specified above.

**Owner-selected default relative Dataset Overview reduction:**

```text
1. compute one selected comparison value independently for each valid Scene;
2. Dataset Overview = arithmetic mean of those valid Scene comparison values.
```

This applies to:

- ratio-of-weighted-means Scene dB values;
- mean-of-grid-log-ratios Scene dB values;
- signed Scene deltas.

Thus the relative Overview is the equal-Scene reduction of the visible Scene Trend.
A future explicitly named pooled-across-Scenes relative mode may be added, but it is
not the schema-v2 default and must not be substituted silently.

This relative default intentionally differs from the absolute Overview default:
absolute Overview defaults to database-wide pooled measurement support, while relative
Overview defaults to equal-Scene aggregation of already formed comparisons. Both are
explicitly labeled semantics rather than two values both called "mean".

## 12. One hierarchy: absolute, relative, and spatial views

The same server-authored measurement model feeds all normal result exploration:

```text
summary metadata
    ├─ pooled absolute Dataset Overview
    └─ absolute Scene Trend

grid sufficient statistics
    ├─ selected-reference Scene comparisons
    │       ├─ Scene Trend
    │       └─ equal-Scene relative Dataset Overview
    └─ grid-retained absolute/relative values
            └─ spatial visualization / P5-D
```

Reference/mode changes may require grid artifacts. The UI may show `Loading...` or
`Calculating...` while bounded asynchronous I/O/numerical work completes.

## 13. Result artifact categories and loading policy

Conceptual layout remains:

```text
result/<job-id>/
    manifest.json
    summary.npz
    scenes/
        scene_000001.npz
        scene_000002.npz
        ...
    detail/
        ... optional per-pixel/debug artifacts ...
```

Artifact categories are defined by purpose:

1. **Summary metadata** — small normal open-time absolute Dataset + Scene summaries.
2. **Grid measurement artifacts** — primary analytical data for exact relative
   calculations and spatial/grid views.
3. **Optional detail artifacts** — larger per-pixel/2K/debug material.

Schema v2 does **not** prescribe "always eager" or "inspected Scene only" for grid
arrays. PixelScope may load them by Scene, bounded batch, background request, or cache
according to measured runtime needs. That policy must remain bounded, stale-safe, and
non-blocking, especially for SMB/network storage.

The expected present workload is up to roughly 300 compared source images. That makes
local vectorized reference switching plausible, but wall-clock latency is not a schema
correctness promise. P5-F owns real size/I/O/cache characterization.

## 14. Spatial visualization

The server does not need to render a heatmap for every target/reference pair.

Absolute spatial view:

```text
absolute grid value -> local display normalization/colormap -> overlay
```

Relative spatial view:

```text
target absolute grid
+ reference absolute grid
+ pair-valid intersection
        ↓
local relative grid
        ↓
local display normalization/colormap
        ↓
viewer/grid visualization
```

Geometry mapping still follows the explicit source/analysis coordinate contract;
PixelScope never treats grid index as source pixel position without that mapping.

## 15. Publication, PARTIAL direction, and immutability

The owner-approved P5 direction remains:

> **Durable PARTIAL results are allowed, and successful Scene work must be
> preservable when another Scene fails.**

Schema v2 does not reopen that decision. What remains deferred to the dedicated P5-C
failure/publication contract is the exact taxonomy and terminal behavior for:

- request-level rejection;
- one bad source/variant inside an N-way Scene;
- missing variants in a PARTIAL Scene;
- per-Scene failure record fields/reasons;
- no-success jobs;
- exact PARTIAL terminal/API identity;
- required artifacts for successful versus failed Scenes;
- cancel/completion/final-publication races.

Incompatible original dimensions or otherwise unevaluable cohorts are rejected or
excluded by server evaluation according to that policy. PixelScope does not repair
them locally.

`manifest.json` remains the immutable publication commit marker unless a later
explicit contract changes it. A result-bearing terminal state is not openable until
all artifacts required for its published successful content are finalized.

Artifact safety remains data-only: path containment, `allow_pickle=False`, declared
dtype/rank/shape, archive/member/array bounds, and no best-effort schema guessing.

## 16. Source inspection remains separate

The measurement schema does not make `source.relative_path` directly openable client
authority. Passive result browsing may display source/variant metadata but must not
interpret a result-relative path as a machine-local file path.

Actual source inspection remains owned by logical storage-root mapping, source
identity/hash validation, and the canonical local registration/selection path in the
later P5 viewer/history slices. Passive browsing does not mutate Files, Selected,
Primary, decoded residency, native Statistics, or Difference.

## 17. Executable-v2 implementation gates

The docs/schema PR freezes the numerical and identity decisions above. Before the
focused executable-v2 domain/fixture/parser slice is considered complete, that slice
must additionally freeze and test:

- exact JSON-versus-NPZ field placement;
- schema-v2 safety ceilings justified by the new summary/grid shape;
- concrete manifest/array names and dtype/shape constraints;
- `measurement_context_id` encoding/fingerprint construction;
- complete/PARTIAL parser discrimination needed by the implemented reader;
- v1 read-only compatibility dispatch;
- golden tests for summary-projection tolerance, grid correspondence, N-way variant
  identity, absolute reductions, and all local comparison modes.

These are **implementation-blocking gates for the executable-v2 migration**, not
choices that P5-B may invent.

The following remain later-phase decisions and do not block this docs/schema PR:

- detailed PARTIAL/failure/cancel taxonomy: P5-C;
- logical-root client configuration ownership: P5-C;
- final grid cache/preload budgets and wall-clock performance targets: P5-F.

## 18. Migration impact on P5 slices

### Historical P5-A / schema v1

PR #37 at `fceb16f6e43c48ec65fbf7ebbcc103b56716b686` remains the merged executable
historical baseline. Its v1 reader/fixtures stay as explicit compatibility coverage.

### Focused executable-v2 migration

After this contract PR merges, a focused domain/fixture/parser migration must land on
`main` before P5-B resumes schema-dependent implementation. It updates versioned
models, reader/writer fixture shape, golden recomposition, N-way identity, summary
verification, and v1 compatibility dispatch without introducing P5-B UI policy.

### P5-B

After the executable-v2 migration merges, the existing P5-B branch must rebase and
reconcile behavior rather than merely resolve Git conflicts:

- use `variant_id` for N-way Reference selection;
- show fast absolute summary views without opening all grids;
- default absolute Dataset Overview to `pooled_weighted_mean`;
- derive selected target/reference comparisons locally;
- default relative Dataset Overview to arithmetic mean of valid Scene comparisons;
- perform required grid I/O/calculation off the UI thread with stale-result rejection;
- preserve passive browsing independence from local source/workspace authority.

### P5-D

P5-D consumes the same absolute grid measurements and derives reference-relative grids
locally before applying the existing exact analysis→source→viewer geometry mapping.

### P5-F

P5-F characterizes realistic result sizes, local numerical latency, SMB/network I/O,
cache/preload policy, and memory bounds. It does not redefine the schema's numerical
meaning to satisfy a timing target.
