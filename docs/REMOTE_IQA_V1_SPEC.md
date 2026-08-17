# Remote IQA v1 normative specification

Status: Normative specialization of `REMOTE_IQA_CONTRACT.md` for P5 v1
Owner: PixelScope P5 program + external IQA server contract
Established: P5-0 independent-review follow-up

This document removes implementation ambiguity before P5-A. Where the broader
`REMOTE_IQA_CONTRACT.md` leaves a P5-v1 detail open, this specification controls.
Production values owned by the GPU implementation are explicit result metadata rather
than PixelScope constants.

## 1. Stable Scene/source/comparison identity

- Every result has stable `scene_id` values.
- Every source has a stable `source_id` unique inside the result.
- A Scene contains ordered `sources[]`; the durable schema is N-source-ready.
- Pairwise comparison records identify both operands by stable source IDs.
- P5 v1 UI is two-source. Its presentation roles are A = first Scene source and
  B = second Scene source.
- A is only the default IQA reference; A/B are not ground-truth/candidate semantics.

For ordered A/B operands:

```text
power raw orientation = A / B
signed orientation    = A - B
```

IQA Reference is feature-local and independent from PixelScope Primary.

## 2. Attribute numerical semantics

Every power AttributeSpec must carry a finite non-negative
`stabilization_epsilon` in the same linear power domain as its reported means.
PixelScope must never hard-code a production epsilon. The external writer owns the
value and the P5-A fixture owns a deterministic test value.

For power attributes:

```text
raw_db(A,B) = 10 * log10((A + epsilon) / (B + epsilon))
```

User-facing directional quality is derived only from `quality_direction`:

```text
higher_is_better → quality_delta_db =  raw_db
lower_is_better  → quality_delta_db = -raw_db
neutral          → no quality_delta_db
```

Thus positive `quality_delta_db` always means A is better for directional attributes.
Raw engineering values remain available.

Luma/Chroma bias use:

```text
signed_delta(A,B) = A - B
```

Bias is neutral/signed and must not be converted to an A-better/B-better dB quality
score. Its final normalized unit definition remains server-versioned metadata.

## 3. Mandatory compact sufficient statistics

Tier-2 compact scene data must provide, for every source / attribute / grid cell:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid_mask
```

The three accumulated numeric values are float64 in v1. `valid_count` is integer and
`valid_mask` boolean. Unweighted attributes use unit weights rather than omitting the
fields.

A block is valid only if:

- `valid_mask` is true;
- `valid_count > 0`;
- `weight_sum > 0`;
- required numeric values are finite;
- declared shape/grid identity is valid.

For valid block set K:

```text
W  = Σ weight_sum[k]
S1 = Σ weighted_sum[k]
S2 = Σ weighted_square_sum[k]
mean = S1 / W
variance = max(0, S2/W - mean*mean)
std = sqrt(variance)
```

The clamp only removes negative floating-point roundoff after otherwise valid finite
inputs.

For A/B, the pairwise valid-grid set is the intersection of A-valid and B-valid cells
for the same Scene/attribute/grid cell index. There is no union or imputation.

## 4. Two official power aggregations

### Ratio of weighted means

Use the common pairwise-valid block set. Aggregate A and B separately in linear space,
then apply the attribute epsilon:

```text
10 * log10((mean_A + epsilon) / (mean_B + epsilon))
```

### Mean of grid log-ratios

For every pairwise-valid cell, compute the source-local block means and the same raw
log ratio. The official summary is the **unweighted arithmetic mean** of those finite
per-cell dB values.

PixelScope must not replace this with a weighted mean of block dB values.

Server-authored official statistics and PixelScope-recomputed values remain distinct
fields even when they agree numerically.

## 5. Invalid/zero-weight representation

Zero total weight, zero pairwise-valid blocks, invalid shape/identity, missing data,
or non-finite required input produces an invalid statistic.

JSON never serializes NaN or Infinity. Invalid scalars use:

```text
value: null
valid: false
invalid_reason: <reason>
```

Initial reasons include `zero_weight`, `no_valid_blocks`, `nonfinite_input`,
`shape_mismatch`, and `missing_data`. Binary artifacts carry explicit validity masks;
NaN is not the sole validity mechanism.

## 6. P5 v1 remote input eligibility

Remote submission v1 accepts only on-disk:

```text
.png  .jpg  .jpeg  .bmp
```

Suffix matching is case-insensitive. `.raw` is rejected for remote submission v1.
PixelScope must not silently demosaic or export a RAW source into a remote RGB input.
The server remains final authority for decoded channel/pixel-layout compatibility.

All sources in one Scene must have equal original width/height; mismatch is an
explicit evaluation error, not an alignment/resize contract between sources.

### Current Pair A/B

`Evaluate Current Pair` is enabled only when the Current Comparison Page contains
exactly two eligible native source documents. Derived Split/Difference documents are
not inputs.

A/B are bound by underlying Current Comparison Page source order, derived from logical
Selected order. Binding must not depend on Primary, Active/focus, viewer tile reorder,
Single/Multi presentation, or Difference presentation order.

## 7. Folder Pair canonical algorithm

P5 v1 forms the ordered list client-side before submission:

1. immediate directory contents only; no recursion;
2. regular non-symlink files only;
3. case-insensitive suffix filter `.png/.jpg/.jpeg/.bmp`;
4. hidden-file attributes do not create a separate filter; an otherwise eligible
   regular file is included;
5. normalize each filename to Unicode NFC;
6. ascending lexical sort by `(normalized_name.casefold(), normalized_name)`;
7. pair A[i] with B[i];
8. unequal counts block submission;
9. show the complete ordered Pair Preview before submit.

This is lexical, not natural/numeric sorting. The explicit Scene manifest freezes the
list; the server must not re-sort it.

## 8. Pixel coordinate convention

Both source and analysis images use continuous **pixel-edge coordinates**.

For width W / height H:

- image boundary extent is `[0,W] × [0,H]`;
- pixel `(i,j)` occupies `[i,i+1) × [j,j+1)`;
- pixel center is `(i+0.5,j+0.5)`.

The result carries a row-major invertible 3×3 affine `source_to_analysis` operating on
homogeneous pixel-edge coordinates:

```text
[x_a,y_a,1]^T = source_to_analysis @ [x_s,y_s,1]^T
```

P5 v1 affine last row is `[0,0,1]`.

`valid_rect = [x,y,width,height]` is the half-open analysis region
`[x,x+width) × [y,y+height)`. Grid origin is the top-left **pixel edge** of cell (0,0).
Cell `(row=r,col=c)` with block `bw×bh` occupies:

```text
[origin_x+c*bw, origin_x+(c+1)*bw)
×
[origin_y+r*bh, origin_y+(r+1)*bh)
```

Only complete cells contained by the valid region are serialized; incomplete borders
are discarded.

Overlay mapping applies inverse(`source_to_analysis`) to the cell-edge polygon,
clips continuously to source `[0,W]×[0,H]`, then uses the existing viewer transform.
No integer rounding occurs before a raster/hit-test boundary requires it.

P5-A must include a non-integer scale plus non-zero valid/grid origin fixture; a 2:1
resize alone is insufficient.

## 9. Result kind/version compatibility

Top-level manifest identity is:

```text
kind = "pixelscope-iqa-result"
schema_version = 1
publication_state = "complete"
```

Reader policy:

- exact kind required;
- schema v1 native;
- unsupported newer schema rejected with clear no-mutation error;
- older schema accepted only through an explicit tested compatibility/migration path;
- no best-effort guessing.

Scene/source comparisons use stable source IDs, not hard-coded `a`/`b` fields as the
only durable structure. P5-A includes at least one small 3-source Scene parser/domain
test even though production P5 v1 UI remains two-source.

## 10. Artifact reference and NumPy safety

All referenced artifacts are relative to the declared result root. Reject references
that are absolute, drive/UNC absolute, contain NUL, escape via `..`, or resolve through
a symlink/reparse target outside the result root.

NPY/NPZ reads are data-only:

- `allow_pickle=False`;
- object/pickle arrays rejected;
- schema-specific dtype validated;
- rank and exact expected shape validated from manifest/grid/source metadata;
- ZIP/NPY metadata inspected before materializing large arrays;
- oversized/malformed data rejected before unbounded allocation/decompression.

Initial v1 parser safety ceilings:

```text
manifest.json                 4 MiB
summary.npz uncompressed     64 MiB
one scene NPZ uncompressed   64 MiB
one compact array            32 MiB
```

These are safety ceilings, not runtime cache budgets. Tier-3 detail artifacts have a
separate future lazy-detail policy.

## 11. Immutable publication boundary

`manifest.json` is the publication commit marker. The external writer must:

1. write/finalize every required Tier-1 and Tier-2 artifact;
2. write `manifest.json.part` with `publication_state="complete"` only after required
   artifacts are finalized;
3. atomically rename/replace it as `manifest.json` on the same result storage;
4. expose job `succeeded` and `/result` only after the final manifest exists.

PixelScope refuses incomplete/unpublished manifests. Tier-3 detail may be absent as an
optional capability. Published Tier-1/2 results are immutable to ordinary clients.

## 12. Inspect Return safety

Passive result browsing never mutates Selected. Explicit Inspect Pair may temporarily
replace local comparison selection through the canonical existing path.

A transient Return snapshot stores only minimum pre-Inspect comparison intent
(Selected order, page anchor, Active, Primary, layout) and is not Session persistence.
IQA-owned Inspect mutations are tracked. If a non-IQA action changes Selected
membership/order, removes a captured source, or replaces/opens a workspace/Session so
that the snapshot is stale, the snapshot is invalidated and Return is disabled rather
than overwriting newer local intent.

P5 v1 blocks Inspect entry while a P4-A temporary curation baseline/Pick Set is active.

## 13. Open Result authority

P5-B establishes the one canonical `Open IQA Result...` parser/controller path using
fixture/local artifacts. P5-E extends **that same path** with production logical-root
reopen, Recent IQA Results, provenance, missing-source/hash diagnostics, and result-only
mode. P5-E must not create a second independent Open Result authority.

P5 does not modify Session v1. Any future IQA-in-Session feature requires an explicit
new Session schema/version decision.

## 14. P5-C owner decision gates

Two operational policies are intentionally not guessed in P5-0 and must be frozen
before P5-C implementation:

1. **logical storage-root client configuration ownership** — typed ApplicationSettings
   with an explicit settings-schema migration versus another already-authoritative
   machine-local configuration mechanism. Result artifacts and Session cannot own
   machine-specific path mappings.
2. **batch failure granularity** — define request-level failure, per-Scene failure,
   whether a durable `partial` terminal result exists, and cancel/completion race
   semantics.

An implementation agent must not invent either policy ad hoc.

## 15. P5-A golden fixture additions

In addition to the broader sample requirements in `REMOTE_IQA_CONTRACT.md`, P5-A must
test:

- explicit epsilon metadata and near-zero golden values;
- A/B raw orientation and noise quality-sign inversion;
- signed bias `A-B`;
- pairwise valid-grid intersection;
- zero-weight/no-valid null+reason behavior;
- mandatory W/S1/S2/count/valid local mean/std recomposition;
- arithmetic mean of per-grid dB versus ratio of aggregate weighted means;
- non-integer affine/crop/origin inverse mapping;
- path traversal, object-array, malformed shape, and oversized-artifact rejection;
- incomplete publication rejection;
- at least one 3-source Scene structural test.
