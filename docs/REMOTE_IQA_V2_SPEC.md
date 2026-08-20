# Remote IQA schema v2 source-measurement specification

Status: Proposed normative replacement for P5 result-schema numerical ownership
Owner: PixelScope P5 program + external IQA server contract
Base discussion: P5-B architecture review after P5-A merge
Target schema identity: `kind = "pixelscope-iqa-result"`, `schema_version = 2`

This document proposes the next durable Remote IQA result contract after the merged
P5-A schema-v1 baseline. It intentionally changes the center of the result model from
**server-authored pairwise comparison records** to **server-authored absolute
per-source measurements**.

The governing principle is:

> **The server owns measurement. PixelScope owns derived comparison, aggregation
> views, and visualization.**

The GPU service remains authoritative for signal extraction, weighting, validity,
analysis-domain geometry, and sufficient statistics for each evaluated image.
PixelScope does not re-run the IQA model and does not reconstruct weighting from
visualization maps. PixelScope consumes server-authored absolute measurements and
constructs reference-dependent relative values, dataset/Scene presentation, and
spatial visualization locally.

This proposal is intended to support N-way comparison directly. A/B remains a useful
presentation for two variants, but the durable model must support three or more
comparison groups without requiring the server to precompute every pairwise
combination.

## 1. Relationship to schema v1

`REMOTE_IQA_V1_SPEC.md` records the merged P5-A schema-v1 baseline and remains the
historical compatibility reference for existing fixtures/readers.

Schema v2 changes these v1 assumptions:

- pairwise comparison records are no longer the numerical source of truth;
- the durable result is organized around absolute measurements for each source;
- a stable comparison-group identity is added across Scenes;
- server-authored fast summaries are separated from grid-level measurement artifacts;
- arbitrary reference/target comparisons are derived locally;
- the former rule that compact Scene artifacts are only a lazy inspection tier is
  removed from the schema contract;
- loading/cache policy becomes a client performance decision rather than part of
  numerical artifact semantics;
- grid-level absolute source measurements become the common input for both derived
  statistics and later spatial visualization.

After this schema revision is accepted and merged, active P5-B work must rebase onto
that merged `main` and adapt to schema v2. The current P5-B branch must not define a
competing schema independently.

## 2. Scene, variant, and source identity

Schema v2 distinguishes a comparison group from an individual image.

- `variant_id` identifies one comparison group/configuration across the dataset.
- `source_id` identifies one concrete image inside a Scene/result.
- every Scene source records both `variant_id` and `source_id`;
- top-level ordered `variants[]` provides stable display/reference ordering;
- Scene order remains stable through `scene_id`;
- source paths/hashes remain historical source identity and are not portable client
  paths by themselves.

Conceptual identity:

```text
Result
├─ Variant A                    # e.g. tuning/configuration A
├─ Variant B
├─ Variant C
└─ Variant D

Scene 0001
├─ Source A-0001 -> variant A
├─ Source B-0001 -> variant B
├─ Source C-0001 -> variant C
└─ Source D-0001 -> variant D

Scene 0002
├─ Source A-0002 -> variant A
├─ Source B-0002 -> variant B
├─ Source C-0002 -> variant C
└─ Source D-0002 -> variant D
```

This identity is required for dataset-level Overview, Scene Trend, reference switching,
and N-way comparison. `source_id` alone must not be overloaded to mean a comparison
configuration across multiple Scenes.

### Published comparison cohort

The normal schema-v2 comparison path assumes a published Scene contains the declared
comparison cohort needed for that result. Source-size/pair eligibility is a server
submission/evaluation concern: invalid pairs/cohorts are not made comparable by the
client.

The detailed failure taxonomy, partial-Scene publication, missing-variant behavior,
and other malformed/ineligible-pair exception rules are deliberately **not frozen in
this proposal**. They remain a separate P5 failure/publication decision track. This
specification only states that PixelScope never rescales/alines incompatible source
images to manufacture a comparison.

## 3. Server numerical authority

For each valid `Scene × source × attribute`, the GPU server owns:

1. source decoding and analysis-domain preparation;
2. attribute signal extraction;
3. attribute-specific weighting/gating policy;
4. valid-cell determination;
5. grid geometry;
6. weighted sufficient statistics;
7. source-local summary statistics;
8. provenance required to interpret those measurements.

PixelScope must not derive an IQA attribute from original pixels and must not recreate
server weights from Edge Map/Texture Gate visualization artifacts.

The server output is an **absolute measurement**, not a judgement against a reference.

## 4. Required grid-level absolute measurements

For every source / attribute / serialized grid cell, the server publishes sufficient
statistics in the attribute's native numerical domain:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid_mask
```

The schema-v1 W/S1/S2/count/valid representation is retained because it preserves
server-authored weighting while allowing deterministic local aggregation.

For one valid source-local cell:

```text
W  = weight_sum
S1 = weighted_sum
S2 = weighted_square_sum
mean = S1 / W
variance = max(0, S2/W - mean*mean)
std = sqrt(variance)
```

`valid_mask=false`, non-positive weight/count, invalid geometry, or non-finite required
inputs makes that source-local cell invalid.

The local client may materialize `grid_mean` as `S1 / W`; the server may additionally
store a convenience mean array, but W/S1/S2/count/valid remain the sufficient
measurement representation unless a later schema explicitly changes it.

Grid geometry, analysis/source transform, valid rectangle, block size, origin, and
border-discard metadata remain explicit and versioned. No fixed analysis scale or
block size is inferred by PixelScope.

## 5. Fast summary metadata

Schema v2 adds server-authored summary metadata so the initial workspace can open
without scanning every grid artifact.

The result must provide absolute summaries at two levels:

### 5.1 Scene-source-attribute summary

For every published `Scene × variant/source × attribute`:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid
mean
std
```

The server-written `mean`/`std` are convenience/authoritative summary values; the
accumulators remain available for provenance and deterministic verification.

These summaries support immediate absolute Scene Trend and source-value inspection
without opening detailed grid arrays.

### 5.2 Dataset-variant-attribute summary

For every `variant × attribute`, the server additionally publishes the aggregation
across all valid published Scenes for that variant:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid
mean
std
```

The intended default dataset absolute mean is a **global weighted aggregation** of the
server measurements, not an unweighted mean of Scene means, unless a later explicit
aggregation mode says otherwise.

Conceptually:

```text
dataset W  = Σ scene/source weight_sum
dataset S1 = Σ scene/source weighted_sum
dataset S2 = Σ scene/source weighted_square_sum
mean       = S1 / W
```

The summary artifact therefore provides a fast path for:

- initial dataset Overview in absolute source/variant terms;
- initial Scene Trend in absolute source/variant terms;
- N-way source/variant browsing before any reference is selected;
- validation that grid recomposition agrees with server summary values.

## 6. Result artifact layout

Conceptual schema-v2 layout:

```text
result/<job-id>/
    manifest.json
    summary.npz                 # fast absolute dataset + Scene summaries
    scenes/
        scene_000001.npz        # absolute grid sufficient statistics
        scene_000002.npz
        ...
    detail/
        ... optional per-pixel/debug artifacts ...
```

The manifest owns:

- result identity/version/publication state;
- ordered `variants[]`;
- ordered Scenes;
- each Scene's source identities and `variant_id` bindings;
- source hashes/logical-storage identity;
- AttributeSpec and stabilization metadata;
- geometry/grid metadata;
- summary/grid/detail artifact references;
- provenance.

The summary artifact is normal-path exploration metadata. Scene grid artifacts are
normal analytical data, not merely an inspected-Scene appendix.

Optional per-pixel/2K maps remain separate large detail artifacts.

## 7. Removal of authoritative pairwise comparison records

Schema v2 does **not** require the server to serialize every possible pairwise
comparison.

For N variants, precomputing all pairs scales as O(N²) per attribute/mode and embeds a
reference policy into the server result. That is unnecessary when the source-local
absolute measurement already contains sufficient information.

The normative result therefore does not use pairwise comparison records as numerical
authority. A server may emit diagnostic/verification comparisons as optional derived
metadata, but PixelScope must not require them for the user-facing calculation path
and they must be distinguishable from source measurements.

## 8. Local reference-dependent comparison

PixelScope selects a `reference_variant_id` and derives comparisons against every
other target variant locally.

For a Scene with A/B/C/D and `reference = B`:

```text
A vs B
C vs B
D vs B
```

Changing the reference to C produces:

```text
A vs C
B vs C
D vs C
```

No server request or server-authored pairwise table is required.

### 8.1 Valid grid support

For an exact target/reference comparison, local calculation uses the intersection of
server-authored valid cells for that target and reference on the same Scene/attribute
grid topology:

```text
pair_valid[g] = valid_target[g] AND valid_reference[g]
```

No union, imputation, implicit resize, or client-generated weighting is permitted.

### 8.2 Power: ratio of weighted means

For the pair-valid cell set, PixelScope aggregates the target and reference absolute
sufficient statistics separately in linear space and applies the server-authored
attribute epsilon:

```text
mean_target = Σ S1_target[g] / Σ W_target[g]
mean_ref    = Σ S1_ref[g]    / Σ W_ref[g]

raw_db = 10 * log10((mean_target + epsilon) / (mean_ref + epsilon))
```

### 8.3 Power: mean of grid log-ratios

For every pair-valid cell:

```text
P_target[g] = S1_target[g] / W_target[g]
P_ref[g]    = S1_ref[g]    / W_ref[g]

grid_db[g] = 10 * log10((P_target[g] + epsilon) / (P_ref[g] + epsilon))
```

The summary is the explicitly defined reduction over those valid grid values. Unless
changed by a future accepted contract, the existing arithmetic-mean semantics remain
the default candidate.

### 8.4 Signed attributes

Signed attributes derive target-reference delta locally from the corresponding
server-authored absolute measurements. They are not converted to a power ratio.

Quality-direction sign remains presentation metadata layered on top of raw engineering
orientation; it must not alter stored absolute source measurements.

## 9. Overview and Scene Trend are views over one source model

Schema v2 deliberately makes Overview and Scene Trend different aggregations of the
same server-authored absolute data rather than separate result products.

### Initial absolute Overview

Use server-written `dataset × variant × attribute` summary metadata.

```text
Attribute X
A absolute mean
B absolute mean
C absolute mean
D absolute mean
```

### Initial absolute Scene Trend

Use server-written `Scene × variant × attribute` summaries while retaining the Scene
axis.

```text
          Scene 1   Scene 2   Scene 3
A         ...       ...       ...
B         ...       ...       ...
C         ...       ...       ...
```

### Relative Overview / Scene Trend

When the user selects a reference or a comparison mode, PixelScope derives the
requested relative values locally from the authoritative measurement source.

- Scene Trend retains each Scene after local target/reference derivation.
- Overview reduces across Scenes according to an explicitly labeled aggregation.
- exact grid-relative values are also the direct input for spatial visualization.

The UI may show `Calculating...` while a required set of compact arrays is read and
derived values are produced.

## 10. Spatial visualization

Spatial IQA visualization is a local presentation over the same absolute grid
measurements.

For an absolute view:

```text
grid absolute power/value -> local normalization/colormap -> overlay
```

For a reference-relative view:

```text
target absolute grid
+ reference absolute grid
+ pair-valid intersection
        ↓
local relative grid
        ↓
local normalization/colormap
        ↓
viewer/grid visualization
```

The server is not required to render heatmap PNGs for every target/reference pair.
Optional server detail maps remain valid diagnostics, but the normal relative spatial
view is derived locally from source-grid measurements.

## 11. Loading and cache policy is not schema semantics

Schema v1 described compact Scene data as a Tier-2 artifact loaded lazily only for
inspected Scenes. Schema v2 removes that requirement from the numerical contract.

The new separation is:

1. **Summary metadata** — small, eager/open-time data for immediate absolute Overview
   and Scene Trend.
2. **Grid measurement artifacts** — primary analytical data used whenever local
   relative calculation or spatial analysis needs them.
3. **Optional detail artifacts** — large per-pixel/debug data loaded only when a
   feature explicitly needs them.

PixelScope may choose to read grid artifacts:

- on the first relative/reference request;
- by Scene;
- by a bounded batch;
- with background preload;
- or from a bounded memory cache.

Those choices are performance/resource policy, not a change in measurement semantics.
The implementation must still remain bounded, stale-safe, and non-blocking for
potential SMB/network storage.

For the expected current workload of up to roughly 300 compared source images, local
vectorized comparison over compact grids is expected to be practical. Wall-clock
latency is not frozen as a correctness contract; P5-F must characterize real result
sizes and SMB behavior before choosing preload/cache defaults.

## 12. Publication and immutability

The immutable publication boundary remains.

A schema-v2 result is not complete/openable until all mandatory manifest, summary,
and required grid measurement artifacts for its published successful cohort are
finalized according to the eventual terminal/failure policy.

`manifest.json` remains the publication commit marker unless a later explicit decision
changes it. Artifact safety remains data-only: relative references, path containment,
`allow_pickle=False`, bounded archive/member/array sizes, declared dtype/rank/shape,
and no best-effort schema guessing.

Exact schema-v2 parser safety ceilings should be chosen when the fixture/reader is
implemented; they need not equal schema-v1 values if the new summary/grid shape
requires justified changes.

## 13. Source inspection remains separate

The source-measurement schema does not make `source.relative_path` directly openable
client authority.

Original source inspection still requires the logical storage-root mapping, source
identity/hash validation, and canonical local registration path owned by later P5
viewer/history slices.

Passive result browsing may show source/variant metadata but must not treat a result
relative path as a machine-local file path or mutate Files/Selected/residency.

## 14. Failure/eligibility policy explicitly deferred

The repository owner has clarified one direction relevant to this schema discussion:
source pairs/cohorts that cannot validly be evaluated, including incompatible source
sizes, are rejected/excluded by server-side evaluation rather than repaired locally.

This document intentionally does not define the complete exception policy for:

- request rejection;
- one bad source within an N-way Scene;
- one failed Scene in a batch;
- missing variants in PARTIAL results;
- no-success jobs;
- corrupt server measurement arrays;
- cancellation/publication races.

Those behaviors must be handled in the dedicated P5-C failure/publication contract so
schema-v2 numerical ownership is not conflated with transport/terminal semantics.

## 15. Migration impact on P5 slices

### P5-A baseline

PR #37/schema v1 remains the executable historical baseline that motivated this
revision. After schema v2 merges, a focused implementation slice must update domain,
fixture, parser, and golden math tests to the accepted v2 structure before later P5
slices rely on it.

### P5-B

The current P5-B branch must remain paused for schema-dependent semantics. After this
schema PR merges to `main`:

1. rebase P5-B onto the new `main`;
2. replace pairwise-comparison authority with absolute source/variant summaries;
3. restore N-way-capable Reference selection;
4. use summary metadata for initial absolute Overview/Scene Trend;
5. perform requested relative calculations locally;
6. keep expensive work off the UI thread and expose calculation/loading state;
7. keep passive browsing independent from Files/Selected/native source authority.

### P5-D

Spatial inspection should consume the same absolute grid measurements and derive
reference-relative grids locally before mapping them through the existing explicit
analysis/source/viewer geometry contract.

### P5-F

Integration hardening must characterize compact artifact size, local calculation
latency, SMB I/O, cache/preload policy, and memory bounds against realistic workloads
rather than assuming all grid artifacts are either always eager or inspected-Scene
only.

## 16. Review questions for this schema PR

Review/orchestration should explicitly confirm or challenge:

1. Is `variant_id` the right stable dataset-level comparison-group identity?
2. Are W/S1/S2/count/valid the correct mandatory source-grid sufficient statistics?
3. Should `mean`/`std` remain explicitly serialized convenience summaries in addition
   to accumulators?
4. Is global weighted aggregation the desired default dataset absolute summary?
5. Should arithmetic mean of valid grid dB remain the second power comparison mode?
6. What exact reducer should relative Overview use across Scenes?
7. Which summary arrays belong in JSON versus NPZ?
8. What safety ceilings are appropriate for schema-v2 summary/grid artifacts?
9. What v1 compatibility policy is required once v2 becomes active?
10. Which failure/PARTIAL semantics must be frozen before v2 reader/server work starts?

These questions are intentionally visible so the schema is reviewed as an engineering
contract before P5-B/P5-C/P5-D code is made dependent on it.
