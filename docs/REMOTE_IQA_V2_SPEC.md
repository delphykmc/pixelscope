# Remote IQA schema v2 source-measurement specification

Status: Executable schema-v2 authority; P5-C PARTIAL extension active in PR #42
Owner: PixelScope P5 program + external IQA server contract
Historical executable baseline: P5-A / PR #37 / schema v1
Durable schema-v2 contract baseline: P5-A2 Stage 1 / PR #39
Executable schema-v2 baseline: P5-A2 Stage 2 / PR #40
Target schema identity: `kind = "pixelscope-iqa-result"`, `schema_version = 2`

This document is the normative contract for PixelScope Remote IQA schema v2. The
governing rule is:

> **The server owns measurement. PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

The GPU service owns source decoding, IQA extraction, Scene-context weighting/gating,
validity, physical analysis/grid geometry, W/S1/S2/count/valid sufficient statistics,
absolute summaries, and measurement provenance. PixelScope does not recompute IQA
from source pixels, reconstruct server weighting from visualization maps, or resize/
align incompatible result grids. It selects a reference `variant_id` and derives
reference-dependent values from the immutable server-authored measurements.

Schema v2 is N-way. A/B is only a two-variant presentation; the stored contract must
support A/B/C/D-style groups without serializing every pairwise combination.

## 1. Versioning and schema-v1 compatibility

`REMOTE_IQA_V1_SPEC.md` remains the historical normative record for the merged P5-A
schema-v1 implementation. Schema v2 does not rewrite v1 artifacts.

The canonical result dispatcher follows this exact policy:

1. `schema_version == 2` -> schema-v2 reader;
2. `schema_version == 1` -> existing schema-v1 read-only reader;
3. any other version -> `UNSUPPORTED`;
4. no v1 result is silently upgraded by inventing v2 absolute measurements from
   pairwise v1 summaries.

The v1 A/B-specific operator strings remain valid only for historical v1 parsing.
New schema-v2 writers use the reference-neutral operator names defined in section 10.

## 2. Identity model

Schema v2 separates four identities:

- `variant_id`: stable comparison/configuration identity across Scenes;
- `source_id`: stable identity of one concrete source image;
- `scene_id`: one evaluation Scene/cohort identity;
- `measurement_context_id`: deterministic identity of the weighted measurement
  context in which the Scene measurements were produced.

Display labels are metadata. They are not durable identity and need not be unique.
Reference selection always uses `variant_id`.

### 2.1 `source_id` reuse across bindings

A concrete source may legitimately participate in more than one Scene/context or in
more than one variant slot of the same Scene. The same `source_id` therefore **may
recur anywhere in one result**, but all occurrences must carry identical immutable
source identity metadata:

```text
source_id
relative_path
sha256
width
height
```

A repeated `source_id` with different immutable source metadata makes a complete v2
manifest invalid.

The reuse rule does **not** authorize weighted-measurement reuse. The same concrete
source evaluated in a different Scene/cohort may have different effective weights,
validity, and summaries; that measurement remains scoped by the Scene's
`measurement_context_id` and the source/attribute binding in that context.

Inside one published successful Scene, `variant_id` is the comparison-slot identity.
Every declared variant is bound exactly once, but two or more variant slots may
intentionally reference the same concrete `source_id`. This permits identical-source
sanity comparisons without inventing a second image identity. Ordered
`(variant_id, source_id, ...)` membership remains part of the context fingerprint, so
this does not make variant bindings ambiguous.

## 3. Published-success Scene structural invariants

For `publication_state = "complete"`, and for every successful Scene retained by a
valid `publication_state = "partial"` result:

- top-level `variant_id` values are unique;
- `attribute_id` values are unique;
- published `scene_id` values are unique;
- every published Scene contains exactly one binding for every top-level variant;
- Scene source bindings are serialized in the exact top-level variant order;
- repeated `source_id` values in the same or different Scenes satisfy section 2.1;
- all variants in one Scene have equal original source dimensions;
- all variants in one Scene carry exactly equal `SceneGeometry` values;
- for each attribute, all variants in one Scene carry exactly equal `GridGeometry`
  values;
- PixelScope never constructs an implicit resize, alignment, imputation, or grid
  correspondence when these invariants fail.

Stage 1 described physical geometry as compatible/equivalent. Stage 2 deliberately
freezes a stricter writer contract: **the duplicated geometry metadata must compare
exactly equal across variants after JSON parsing**. The server writer must canonicalize
its shared Scene/grid geometry before publishing the per-source copies. A future
schema version may move geometry into shared records or define a tolerance; v2 does
not.

P5-C does not encode a missing variant by publishing a structurally incomplete Scene.
A requested Scene whose cohort cannot produce the complete published shape is instead
represented by a failed/cancelled `scene_outcome` and is absent from `scenes[]`.

## 4. Scene measurement context and deterministic fingerprint

An absolute source measurement is reference-independent **inside one published Scene
measurement context**. It is not globally context-free.

The executable v2 context identity is:

```text
mc2:<64 lowercase SHA-256 hexadecimal characters>
```

The digest is SHA-256 over UTF-8 canonical JSON with sorted keys, compact separators,
`ensure_ascii=False`, and `allow_nan=False`. Floating geometry tokens are serialized
with Python `float.hex()` before hashing.

The canonical payload binds:

- schema token `pixelscope-iqa-measurement-context-v2`;
- `scene_id`;
- ordered Scene source membership;
- each source's `variant_id`, `source_id`, SHA-256, width, and height;
- analysis width/height, 3x3 source-to-analysis affine, and valid rectangle;
- per-attribute grid rows/columns, block size, origin, and discarded borders;
- attribute identity, value kind, and weighting provenance;
- representative identity/policy;
- preprocessing/profile identity;
- model identity;
- weighting/gating identity;
- geometry-profile identity.

Display labels and reference choice do not participate because they do not change the
published absolute measurement. Comparison operator, quality direction, and epsilon
also do not change the server-authored W/S1/S2 measurement and therefore are not part
of this measurement-context fingerprint.

A manifest whose supplied `measurement_context_id` does not exactly match the
recomputed fingerprint is invalid.

## 5. Server numerical authority

For each valid `Scene x source x attribute`, the server owns:

1. source decoding and analysis-domain preparation;
2. IQA attribute extraction;
3. Scene-context weighting/gating;
4. grid/source validity decisions;
5. analysis and grid geometry;
6. W/S1/S2/count/valid sufficient statistics;
7. absolute Scene and Dataset summary projections;
8. context/model/profile provenance.

PixelScope consumes these measurements. It must not recompute the IQA signal from
source pixels or derive effective weights from Edge Map/Texture Gate detail data.

## 6. Grid sufficient statistics

For every `Scene x variant/source x attribute x grid cell`, the server publishes:

```text
weight_sum              W   float64
weighted_sum            S1  float64
weighted_square_sum     S2  float64
valid_count                  int32
valid_mask                   bool
```

For an explicit-valid cell:

```text
mean = S1 / W
variance = max(0, S2 / W - mean * mean)
std = sqrt(variance)
```

Explicit-valid cells require finite W/S1/S2, positive W, positive count, and
non-negative S2. Power-domain S1/mean must be non-negative. A tiny negative variance
caused by floating roundoff may be clamped to zero using the executable numerical
tolerance; a materially negative variance is corrupt.

Cells with `valid_mask == false` do not contribute to reductions. Invalid Scene
summaries use zero W/S1/S2/count and false validity.

## 7. Canonical absolute Scene reduction

The canonical Scene scalar uses all explicit-valid source-local cells:

```text
scene_W  = sum(W[g])
scene_S1 = sum(S1[g])
scene_S2 = sum(S2[g])

weighted_mean = scene_S1 / scene_W
weighted_variance = max(0, scene_S2 / scene_W - weighted_mean**2)
weighted_std = sqrt(weighted_variance)
```

`sum(S1) / sum(W)` is the only canonical Scene mean. Arithmetic mean of cell means is
not interchangeable with it.

## 8. Dataset absolute summaries

For every `variant x attribute`, v2 publishes two separately named reductions.

### 8.1 Pooled measurement summary

```text
pooled_W  = sum(valid scene_W)
pooled_S1 = sum(valid scene_S1)
pooled_S2 = sum(valid scene_S2)
```

Mean/std are recomposed from those pooled accumulators. The default absolute Dataset
Overview is `pooled_weighted_mean`.

### 8.2 Equal-Scene summary

Let `m[s]` be each valid canonical Scene `weighted_mean`:

```text
scene_mean  = arithmetic_mean(m[s])
scene_std   = population_std(m[s])
scene_count = number of valid Scene means
```

This is a different statistic; each valid Scene contributes one sample regardless of
its effective support.

For PARTIAL, Dataset summaries are defined only over the published successful
`scenes[]`; failed/cancelled requested Scenes contribute no synthetic zero or imputed
measurement.

## 9. Serialized projections and numerical consistency

W/S1/S2/count/valid plus this specification's formulas are the numerical authority.
Serialized mean/std values are fast projections only.

For finite floating values `a` and `b`, projection consistency is:

```text
abs(a - b) <= max(1e-12, 1e-9 * max(abs(a), abs(b)))
```

Counts and validity agree exactly. Dataset pooled accumulators must equal the sums of
contributing Scene accumulators under the same floating projection rule. Equal-Scene
mean/std/count must match deterministic reduction of the published valid Scene means.
A disagreement is corrupt; the client never chooses whichever representation is more
convenient.

## 10. Reference-neutral comparison operators

Schema-v2 AttributeSpec serializes one of these reference-neutral operators:

```text
power_ratio_target_over_reference_db
signed_target_minus_reference
```

The historical v1 names `power_ratio_a_over_b_db` and `signed_a_minus_b` are not valid
v2 writer values. The words target/reference denote the operands selected locally at
runtime and are never fixed top-level A/B variant identities.

### 10.1 Pair-valid support

For a Scene/attribute whose cross-variant geometry is already validated:

```text
pair_valid[g] = valid_target[g] AND valid_reference[g]
```

There is no union, imputation, resize, alignment, or client-generated weighting.

### 10.2 Power mode 1 — ratio of weighted means

For pair-valid set K:

```text
mean_target = sum(K, S1_target) / sum(K, W_target)
mean_ref    = sum(K, S1_ref)    / sum(K, W_ref)
raw_db = 10 * log10((mean_target + epsilon) / (mean_ref + epsilon))
```

`epsilon` is mandatory, finite, non-negative server-authored metadata in the same
linear power domain.

### 10.3 Power mode 2 — mean of finite grid log-ratios

For each pair-valid cell:

```text
P_target[g] = S1_target[g] / W_target[g]
P_ref[g]    = S1_ref[g]    / W_ref[g]
grid_db[g]  = 10 * log10((P_target[g] + epsilon) / (P_ref[g] + epsilon))
```

The Scene value is the **unweighted arithmetic mean of the finite `grid_db[g]`
values only**. A pair-valid cell whose ratio is undefined/non-finite, for example
`0/0` when `epsilon == 0`, contributes no Mode-2 sample; another pair-valid cell with
a finite ratio still contributes normally. If no finite grid dB value remains, Mode
2 is invalid with explicit no-finite-grid-ratio semantics. Negative power-domain
cell means are invalid input rather than values to skip.

Mode 2 is intentionally not a weighted mean of dB cells and need not equal mode 1.
Historical schema-v1 behavior is not changed by this v2 rule.

### 10.4 Signed attributes

For signed attributes, each source mean is recomputed over the common pair-valid
support and:

```text
raw_delta = mean_target - mean_reference
```

Signed attributes use `quality_direction = neutral` and do not emit a quality delta.

## 11. Central quality-direction semantics

The Qt-free v2 comparison layer is the single authority for both engineering-oriented
raw values and user-facing quality orientation:

```text
raw relative value      # target/reference engineering orientation
quality relative value  # positive means target quality is better
```

For both power modes:

- `higher_is_better`: `quality = raw`;
- `lower_is_better`: `quality = -raw`;
- `neutral`: quality is explicitly not applicable.

Signed attributes are neutral and therefore expose only their raw signed delta. P5-B
plots/tables must consume this authority rather than implementing their own sign rule.
Reversing target/reference reverses the raw value and, for non-neutral power
attributes, reverses the quality value as well.

## 12. Relative Dataset reduction

For a selected reference and comparison mode, PixelScope first computes one local
comparison independently for each valid published Scene. The default relative Dataset
Overview is then the arithmetic mean of those valid Scene comparison values.

This equal-Scene reduction applies to mode-1 power dB, mode-2 power dB, and signed
Scene deltas. A future pooled-across-Scenes relative statistic must have a distinct
name and cannot silently replace this default.

## 13. Concrete artifact layout

The executable v2 layout is:

```text
result/
    manifest.json
    summary.npz
    scenes/
        scene_000000.npz
        scene_000001.npz
        ...
    detail/
        ... optional opaque artifacts ...
```

`manifest.json` is the immutable publication commit marker and is written last.

### 13.1 Manifest JSON

Required common top-level fields are:

```text
kind                    "pixelscope-iqa-result"
schema_version          2
publication_state       "complete" | "partial"
result_id               string
variants[]              ordered {variant_id, label}
attributes[]            ordered AttributeSpec records
summary_artifact        {path, uncompressed_size}
scenes[]                ordered published successful Scene records
```

A PARTIAL manifest additionally requires `scene_outcomes[]` as defined in section 16.
A COMPLETE manifest is the all-success shape and does not require partial diagnostics.

Each published successful Scene contains:

```text
scene_id
measurement_context_id
context_provenance {
    representative_id,
    preprocessing_id,
    model_id,
    weighting_id,
    geometry_id
}
sources[]               exact top-level variant order
grid_artifact           {path, uncompressed_size}
detail_artifacts[]      optional opaque relative-path strings
```

Each source binding contains `variant_id`, immutable source metadata, one complete
`geometry` record, and a `grids` object containing exactly every declared attribute.
Repeated concrete `source_id` values are permitted as described in section 2.1.

`detail_artifacts[]` is intentionally **opaque in schema v2 Stage 2/P5-C**. A bare path
is only a bounded reference and is not a permanent P5-D decode contract. P5-D may
define a separately versioned typed detail sub-schema containing kind/dtype/shape/
size/geometry metadata before consuming such data. Current readers never infer detail
dtype or meaning from the path.

### 13.2 `summary.npz`

For `S = published successful scene_count`, `V = variant_count`, `A = attribute_count`:

| Array | dtype | shape |
| --- | --- | --- |
| `scene_ids` | `<U128` | `(S,)` |
| `variant_ids` | `<U128` | `(V,)` |
| `attribute_ids` | `<U64` | `(A,)` |
| `source_ids` | `<U128` | `(S,V)` |
| `measurement_context_ids` | `<U68` | `(S,)` |
| `scene_weight_sum` | `float64` | `(S,V,A)` |
| `scene_weighted_sum` | `float64` | `(S,V,A)` |
| `scene_weighted_square_sum` | `float64` | `(S,V,A)` |
| `scene_valid_count` | `int64` | `(S,V,A)` |
| `scene_valid` | `bool` | `(S,V,A)` |
| `scene_weighted_mean` | `float64` | `(S,V,A)` |
| `scene_weighted_std` | `float64` | `(S,V,A)` |
| `pooled_weight_sum` | `float64` | `(V,A)` |
| `pooled_weighted_sum` | `float64` | `(V,A)` |
| `pooled_weighted_square_sum` | `float64` | `(V,A)` |
| `pooled_valid_count` | `int64` | `(V,A)` |
| `pooled_valid` | `bool` | `(V,A)` |
| `pooled_weighted_mean` | `float64` | `(V,A)` |
| `pooled_weighted_std` | `float64` | `(V,A)` |
| `scene_mean` | `float64` | `(V,A)` |
| `scene_std` | `float64` | `(V,A)` |
| `scene_count` | `int32` | `(V,A)` |
| `equal_scene_valid` | `bool` | `(V,A)` |

Invalid summary projection slots are serialized as zero while their validity flag is
false; the domain representation exposes their mean/std as absent rather than as
numerical zero.

### 13.3 Scene grid NPZ

Every published Scene grid artifact contains:

```text
variant_ids                <U128  (V,)
source_ids                 <U128  (V,)
measurement_context_id     <U68   (1,)
```

For each attribute `<id>` with rows R and columns C:

```text
<id>__weight_sum               float64  (V,R,C)
<id>__weighted_sum             float64  (V,R,C)
<id>__weighted_square_sum      float64  (V,R,C)
<id>__valid_count              int32    (V,R,C)
<id>__valid_mask               bool     (V,R,C)
```

Member names, dtype, rank, shape, variant order, source order, and context identity
match exactly. Object/pickle arrays are rejected.

## 14. Summary-first filesystem boundary

Ordinary `load_result_v2()` performs filesystem I/O only for `manifest.json` and the
referenced `summary.npz`. Scene-grid and optional-detail references are validated
syntactically during manifest parsing, including POSIX and Windows absolute/traversal
semantics, but their existence, symlink-resolved containment, file type, archive
metadata, and array contents are deferred.

`load_grid_scene()` is the boundary that resolves and opens one requested published
Scene grid. Therefore ordinary result open does not perform O(Scene) stat/resolve
operations over SMB merely to establish the overview. P5-F still owns measured
cache/preload and network-I/O policy.

A missing/corrupt deferred grid does not prevent the absolute summary-first result
from opening; requesting that Scene grid returns a corrupt grid-load outcome.

## 15. Artifact/path safety ceilings

The executable v2 parser uses safety ceilings rather than runtime cache budgets:

| Limit | Value |
| --- | ---: |
| manifest JSON | 8 MiB |
| summary NPZ uncompressed | 128 MiB |
| one Scene NPZ uncompressed | 128 MiB |
| one ndarray payload | 32 MiB |
| one NPY member metadata/file size | 32 MiB + 64 KiB |
| one archive on disk | 130 MiB |
| NPZ members per artifact | 192 |
| variants | 32 |
| requested/PARTIAL outcomes Scenes | 512 |
| published successful Scenes | 512 |
| attributes | 32 |
| total published Scene source bindings | 1024 |
| grid cells per attribute | 65,536 |
| detail references per Scene | 64 |
| generic ID length | 128 characters |
| display label | 256 characters |
| provenance string | 512 characters |
| source relative path | 2,048 characters |
| artifact reference | 1,024 characters |

The `1024` aggregate published source-binding ceiling is a deliberate result-acceptance
safety envelope, not a cache budget. P5 Stage-1 planning targeted roughly 300 compared
source images, so 1024 provides more than 3x headroom for that production assumption
while also bounding manifest/summary cardinality before allocation. It permits the
full 512 Scenes for the initial two-variant P5-C workflow, about 341 complete Scenes
for a three-variant externally produced result, and 256 for four variants. P5-B may
explore N-way results inside this envelope. A future production requirement beyond it
must trigger an explicit schema/safety review and coordinated server/client change
rather than a silent local override. The independent byte ceilings above remain
additional bounds, not substitutes for this cardinality guard.

NPZ input must be data-only. The reader rejects malformed ZIP/NPY structures,
duplicate members, encrypted members, unsupported compression, unexpected members,
object/pickle dtype, wrong dtype/rank/shape, oversized arrays/members/archives, and
declared/actual uncompressed-size mismatch. `np.load(..., allow_pickle=False)` remains
mandatory.

Artifact references reject NUL, POSIX absolute paths, Windows absolute/drive paths,
UNC paths, and `..` traversal under both POSIX and Windows path semantics. Deferred
artifact containment is rechecked against the resolved result root when the artifact
is actually opened.

## 16. Publication state and executable PARTIAL contract

Schema v2 supports exactly two published artifact states:

- `publication_state = "complete"` -> all requested Scenes succeeded;
- `publication_state = "partial"` -> at least one requested Scene succeeded and at
  least one requested Scene failed or was cancelled.

Any other artifact publication state is invalid.

A valid PARTIAL manifest requires ordered `scene_outcomes[]`. It is a bounded list of
all requested Scene terminal outcomes in original request order. Each entry contains:

```text
scene_id
status                  "succeeded" | "failed" | "cancelled"
error {                 required only for failed/cancelled
    code                non-empty bounded string, max 128 chars
    message             non-empty bounded string, max 512 chars
    retryable           optional boolean
}
```

Rules:

- `scene_outcomes` contains 2..512 unique `scene_id` values;
- `succeeded` entries must not contain `error`;
- `failed`/`cancelled` entries require bounded error diagnostics;
- PARTIAL requires at least one `succeeded` outcome;
- PARTIAL requires at least one `failed` or `cancelled` outcome;
- the ordered IDs of all `succeeded` outcomes must exactly equal the ordered
  `scenes[].scene_id` values;
- `scenes[]`, `summary.npz`, and Scene-grid artifacts contain only successful fully
  published Scenes;
- every successful PARTIAL Scene is parsed by the same complete-Scene structural,
  numerical, context, geometry, projection, and artifact rules as COMPLETE;
- failed/cancelled requested Scenes do not contribute fabricated zeros, placeholders,
  source bindings, summaries, or grids;
- zero-success terminal work is not a PARTIAL artifact; the job terminates `failed`
  or `cancelled` and exposes no published result reference;
- all-success terminal work is `succeeded` with a COMPLETE artifact.

This representation intentionally preserves successful Scene work without creating a
second numerical authority or a relaxed incomplete-Scene schema.

## 17. Source inspection remains separate

`source.relative_path` is historical/logical source metadata, not direct machine-local
open authority. Passive result browsing must not mutate Files, Selected, Primary,
decoded residency, Statistics, Difference, or the current comparison workspace.

P5-C logical result resolution uses configured `storage_root_id + relative_path` for
the result artifact itself. Native source Inspect still belongs to the later P5-D
contract and requires explicit source logical-root/hash verification before canonical
local registration/selection.

## 18. Executable acceptance and compatibility gates

The merged P5-A2 Stage-2 coverage establishes the complete-result schema-v2 baseline:

- deterministic v2 N-way fixture round-trip and identity ordering;
- the real existing schema-v1 fixture through canonical version dispatch;
- hand-calculated weighted Scene reduction and comparison constants;
- pooled versus equal-Scene Dataset summaries;
- both power modes and their deliberate divergence;
- Mode-2 mixed finite/undefined grid-ratio reduction and no-finite-ratio behavior;
- signed target/reference delta and reference reversal;
- centralized higher/lower/neutral quality-direction semantics;
- pair-valid intersection and equal-Scene relative Dataset reduction;
- projection tolerance and corrupted projections;
- context fingerprint determinism/tampering;
- complete cardinality, exact geometry/grid correspondence, cross-Scene source reuse,
  and identical-source multi-variant binding;
- negative/non-finite/zero power and epsilon behavior;
- POSIX/Windows path escapes;
- malformed/duplicate/encrypted/unsupported/object/wrong-shape/wrong-dtype/oversized NPZ;
- summary-first deferred-grid behavior;
- future-version handling.

P5-C adds executable PARTIAL coverage for ordered Scene outcomes, success/failure/
cancelled diagnostics, zero-success/all-success rejection, successful-Scene ordering,
and COMPLETE/PARTIAL canonical loader compatibility. P5-C debug fixtures must reuse
the canonical v2 fixture/result-loader path rather than defining independent result
math.

Observed validation is recorded separately from planned commands. Repository standard
checks for changed `src/`, `tests/`, and docs remain the merge gate: focused/full
pytest, Ruff, mypy, docs checks, `pip check`, and `git diff --check`.

No silent v1→v2 numerical upgrade is allowed.
