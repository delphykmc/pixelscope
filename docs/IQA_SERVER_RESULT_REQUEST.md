# IQA compute/shared-storage result contract request v0.1

Status: **proposal for server-team negotiation**, not an existing server implementation or finalized proprietary wire schema. Tracking: [#140](https://github.com/delphykmc/pixelscope/issues/140). Client ownership: [#139](https://github.com/delphykmc/pixelscope/issues/139). Handoff implementation: [#141](https://github.com/delphykmc/pixelscope/issues/141).

## Request to the compute/shared-data-service owners

Please return (1) feasibility and deviations, (2) sanitized complete+partial fixture, (3) schemas with formula/sign/aggregation definitions, (4) publication/lifecycle protocol, (5) provisional source recovery/retention policy. Actual enterprise storage roots, URLs, credentials, transport and security config must be agreed **inside the private environment**, not in PUBLIC MAIN issues/docs.

### Fixed client use-case

- Exactly **one pair** A and B; pixel-aligned RGB, same width/height. Expected native 4K input; **do not downscale for the Client contract**.
- Roughly 10–12 Attributes, most in dB, a small minority signed delta. Attribute order is supplied by the server; each has a stable ID, display label, group/unit, value kind, raw higher/lower-is-better or neutral semantics and formula/version identity.
- User-oriented relative comparison: **positive => A better; negative => B better**, only if quality orientation is defined. The user may flip comparison direction in the UI; never infer quality winner for neutral metrics.
- Official global relative comparison is distinct from (a) raw A/B scores, (b) mean of spatial dB cell values, and (c) Client-derived ROI statistics. Explicitly identify official comparison mode and operand order; ratio-of-means and mean-of-log-ratios may differ.
- Per-Attribute relative spatial grid and mask; nominal cells cover about 64 x 64 original pixels at 4K, but every Attribute publishes **actual** rows, columns, origins, block extents and trailing/partial cell policy.
- A/B source RGB files may become inaccessible: numeric and spatial results must still be readable.
- Client visualization uses fixed comparable unit/Attribute-specific bipolar color ranges, **not** robust percentile or result-dependent auto contrast. Highlight clipping and allow user range adjustment; never mutate numeric results.
- One analysis Window, independently opened from saved file; server Job need not exist when result is inspected.

## Transport-agnostic job/state control (P0)

| Operation | Contract |
|---|---|
| Submit | Client request/idempotency key, stable input source references for A/B, Job ID or explicitly uncertain submit outcome; do not resubmit an ambiguous request blindly |
| Poll status | Stable Job ID; QUEUED/RUNNING/COMPLETED/FAILED/CANCELLED (cancel if supported); progress optional; sanitized diagnostics |
| Completion | Job terminal success; distinguish **COMPLETED execution** from **RESULT_PUBLISHED / materializable artifact** |
| Get result | Stable opaque Result ID / locator independent of execution process; missing/partial/failed explicit |
| Cancel | Optional capability; local UI dismiss ≠ backend job cancel; cancellation outcome authoritative |
| Recovery | Rerun/restart should resolve an accepted request/Job where supported without duplicate computation |

Exact transport (HTTP, RPC, filesystem notification, database) and auth are not specified in PUBLIC.

## Suggested immutable published directory (P0)

```text
{run_id}/
    request.json                      # optional auditable input snapshot
    results/
        {result_id}/
            manifest.json            # required: discovery/semantics/paths
            summary.json             # required: OFFICIAL pairwise global comparisons
            spatial/
                {attribute_id}.npz    # proposed numeric array containers
            reports/                 # optional; no dependence
            _READY.json              # commit/publish marker, LAST
```

This is a **logical proposal**, not a required physical share root or filename set. A different server-native tree is acceptable with equivalent manifest/artifact discovery. Paths inside manifests must be **relative, canonical and confined under the result root**; no traversal, absolute shared paths, signed URLs or credentials in portable metadata.

**Publish protocol:** write all artifacts to a private staging/pending location; validate integrity; then publish a single immutable result snapshot. A ready marker is a suitable last step if atomic folder rename is not available. A client must not trust listing a directory alone; only open a committed result. Once READY, files are immutable. Failures/partial result publication must have a documented terminal completeness state.

## Required manifest metadata (P0)

The following are logical fields, not finalized JSON keys:

| Category | Required |
|---|---|
| Envelope | artifact/schema version, Result ID, Run/Job correlation where available, generated-at, status/completeness |
| Pair | image A/B immutable source IDs, SHA-256 or equivalent strong content identifiers, source width/height, RGB channel order/encoding as relevant, pixel-aligned=true |
| Attribute | stable ID, display name, declared order, kind (power/signed), raw quality direction, unit, comparison formula/version and parameter provenance safe to disclose |
| Official summary link | per Attribute value, numeric unit, comparison operands and orientation, validity reason; optional uncertainty/sample count |
| Spatial link | per Attribute NPZ artifact path, array keys, expected shapes/dtypes, grid origin/extent, mapping to original image coordinates, valid_rect/edge rules |
| Integrity | artifact bytes, SHA-256, optional uncompressed size and array item limits; no object/pickle arrays |
| Status | AVAILABLE/PARTIAL/MISSING/FAILED and sanitized per Attribute/spatial diagnostics; missing never silently zero |

### Illustrative skeleton (synthetic; API names negotiable)

```json
{
  "schema_version": "0.1-proposal",
  "result_id": "example-result",
  "completeness": "complete",
  "pair": {
    "image_a": {"source_id": "source-a", "sha256": "example-sha256-a", "width": 3840, "height": 2160, "channels": 3},
    "image_b": {"source_id": "source-b", "sha256": "example-sha256-b", "width": 3840, "height": 2160, "channels": 3},
    "pixel_aligned": true
  },
  "comparison_sign": {"positive": "A_better", "negative": "B_better"},
  "attributes": [
    {
      "id": "attribute_01", "display_order": 0, "unit": "dB",
      "raw_quality_direction": "lower_is_better",
      "comparison_mode": "server-defined-aggregation-v1",
      "summary_ref": "summary.json#attribute_01",
      "spatial_ref": "spatial/attribute_01.npz",
      "grid": {
        "rows": 34, "columns": 60,
        "block_width": 64, "block_height": 64,
        "origin_x": 0, "origin_y": 0, "edge_policy": "partial_trailing_blocks"
      }
    }
  ],
  "artifacts": [
    {"path": "summary.json", "sha256": "example-digest", "bytes": 1234},
    {"path": "spatial/attribute_01.npz", "sha256": "example-digest", "bytes": 5678}
  ]
}
```

The 3840×2160 / 64×64 example yields 60 columns and **34 rows** with a partial final row. This is an illustration, not a promise of actual model grid geometry. Source paths/hints must not be used as identity without integrity checking.

## Official summary (P0)

Each Attribute requires an **official full-pair relative comparison**, or an explicit MISSING state if the producer cannot supply one. Include:

- relative value, availability/diagnostic, unit, sign orientation (quality-oriented or raw), comparison operator/formula ID+version, comparison aggregation mode (e.g. ratio of weighted means vs mean grid log ratios), valid support/weight if meaningful;
- A and B absolute/raw values are desirable but optional, not a substitute for an official comparison;
- if raw sign is provided, specify quality direction so adapter can transform to +A/-B without reverse-engineering; neutral metrics must stay non-ranking;
- do not assume that subtracting two independently rounded dB values produces the correct official comparison.

## Spatial NPZ proposal (P0)

One NPZ per Attribute is acceptable at ~2,040 cells per Attribute for nominal 3840×2160 / 64 blocks. NPZ is a container, **not** the semantics contract. Possible named arrays:

| Key | Example dtype | Shape | Requirement |
|---|---|---|---|
| `relative_value` | little-endian float32/64 | (rows, cols) | Required; clear orientation and unit |
| `valid_mask` | bool | (rows, cols) | Required; false is invalid, not numerical zero |
| `valid_count` | uint32 | (rows, cols) | Recommended if meaningful |
| `weight_sum` | float32/64 | (rows, cols) | Recommended if meaningful |
| `aggregate_numerator` / `aggregate_denominator` | float64 | (rows, cols) | Optional metric-specific **sufficient statistics** for exact ROI aggregation |

Actual sufficient statistics depend on the formula; never imply these names alone guarantee exact ROI reconstruction. If array shapes differ by attribute, publish explicit geometry. Invalid values may be NaN but mask is authoritative, and numeric arrays must not contain unmasked nonfinite values. Client must enforce bounded decompression, dtype/shape/endian, checksum and use `numpy.load(..., allow_pickle=False)` or an equivalent safe reader. If another container is preferable for partial reads, ask the server to propose it with justification.

## Offline ROI aggregation request (P1)

Client computes sliding-window hotspots (default ROI 512×512, Top 3–5, non-max suppression), ROI-local grid statistics and cross-attribute inspection. Client MUST label derived grid means as such rather than misrepresenting them as official results.

Please specify for each metric:
1. Can official ROI comparison be reconstructed from per-cell sufficient stats? Which weights and transformation are required?
2. Is it instead necessary to request a server-side ROI calculation (optional endpoint)? If so, how are coordinate/boundary rules defined?
3. If neither, provide clear guidance on approximate grid-derived means with validity/coverage ratios.
4. How do partial cells, invalid masks, low sample count and denominator stabilization work?

## Client-only persistence/reporting

Server need only publish immutable, complete Result artifacts. PixelScope SUB Client owns `Open Result...` from disk, `Save Result As...` in a portable validated package (e.g. a versioned ZIP bundle with JSON/NPZ plus a separate `analysis_state.json`), and Export CSV/images/standalone HTML. Original RGB may be absent. Analysis State (selected Attribute, ROI, cursor, zoom, fixed-color range) is not an official model result. The portable format is **not** a server deliverable.

## Server response / acceptance checklist

- [ ] Confirm JSON+NPZ or propose an equivalent with openability and precise semantic keys.
- [ ] Confirm official global pairwise comparisons and positive/negative semantics for both dB and signed delta.
- [ ] Provide at least one **public-safe or private-only, appropriately located** complete two-Attribute sample (dB/signed) and one partial/missing sample. Do not publish proprietary data to PUBLIC.
- [ ] Provide grid geometry, masks, trailing block rule and sample/weight details.
- [ ] Specify completed-vs-ready, immutable publication, marker/checksums and retries.
- [ ] Specify schema migration/version changes and unknown-field tolerance.
- [ ] Confirm job idempotency and any backend cancel/recovery capability.
- [ ] Mark ROI sufficient-stats feasibility and describe metric-specific aggregation.
- [ ] Note any incompatibility with the proposal for iterative adapter negotiation.

**Boundary:** All real endpoints, internal directory roots, credentials, datasets and algorithm details belong to PRIVATE SUB. Public MAIN schema additions, if needed, use company-neutral types/fixtures and a separate reviewed PR.
