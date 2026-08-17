# Remote IQA contract

Status: P5 planning contract
Owner: PixelScope P5 program + external IQA server contract
Established: P5-0

This document defines the product/data boundary for PixelScope P5. The external GPU
IQA implementation lives in a separate repository. PixelScope consumes a stable job
and result contract; it does not reimplement the server's signal extraction models.

## 1. Product goal

P5 adds a workflow in which a user can:

1. inspect images quickly with the existing PixelScope local comparison tools;
2. submit the current pair or a large two-folder evaluation to a GPU IQA service;
3. continue normal PixelScope work while a remote job runs;
4. reopen durable historical IQA results without rerunning the GPU job;
5. explore results hierarchically from dataset trend to attribute, scene, and
   spatial block;
6. inspect selected IQA scenes in the existing PixelScope viewer without turning IQA
   state into a second source/residency/selection authority.

## 2. Existing PixelScope authority remains unchanged

P5 inherits this runtime hierarchy unchanged:

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
local Statistics, Histogram, Line Profile, Difference, source protection, and page
loading.

Remote IQA is feature-local state. IQA result membership must not itself:

- register or decode every batch input;
- protect source residency;
- start PixelScope preload;
- change source generations;
- redefine Difference/cache identity;
- redefine Display Gain/native analysis semantics;
- persist runtime arrays into PixelScope Session v1.

## 3. Remote IQA authority model

The server-side conceptual hierarchy is:

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

A **Scene** is the unit that shares structural context. In P5 v1 UI, a Scene contains
exactly two sources. The schema/result model should be N-source-ready so a future
workflow can compare a reference plus multiple variants without redesigning the
artifact format.

The first source is the default comparison reference only. A/B are left/right roles,
not an intrinsic reference/candidate truth.

## 4. Common scene context

For multiple captures of the same scene, the GPU pipeline creates a representative
image and derives common structural context from it:

- a PiDiNet-derived continuous Edge Map;
- a continuous Texture Gate from the server's texture network.

Edge values near 1 indicate stronger edge structure and values near 0 indicate
flatter regions. Texture Gate values near 1 indicate edge/texture structure and
values near 0 indicate flatter structure. Both maps are used by the server because
they encode complementary information.

The structural maps are **scene-common**, not source-local and not comparison-local.

The server may use soft weighting, hard gating, thresholds, or other versioned
configuration. PixelScope must not infer the server's effective numerical weighting
from Edge Map / Texture Gate values. The server's reported statistics and effective
block statistics are the numerical authority. Structural maps are optional detail
artifacts for inspection/provenance unless a future contract explicitly exposes a
reproducible weighting formula.

## 5. Attribute contract

P5 starts with ten IQA attributes:

| Attribute | Quality direction | Initial block size |
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

The block sizes above are current defaults, **not client constants**. Every result
must carry attribute/grid metadata. Server algorithm/profile changes may change grid
size without requiring PixelScope source-code changes.

Attribute metadata must be sufficient to distinguish at least:

- stable attribute ID and display name;
- value kind (`power` or `signed` initially);
- comparison operator;
- quality direction;
- unit/normalization metadata;
- block width/height in analysis-domain pixels;
- grid origin, width, and height;
- server weighting/profile metadata relevant to interpretation.

### Directional power attributes

For power-like directional attributes, the raw spatial comparison is normally a
power ratio in dB:

```text
10 * log10((A + epsilon) / (B + epsilon))
```

Raw mathematical sign and user-facing quality interpretation are separate. For
noise, larger raw power is worse; for detail/edge/contrast/colorfulness, larger raw
power is better.

The UI should therefore expose a normalized semantic direction where useful, such as
`B better ← 0 → A better`, while retaining raw values in engineering detail views.

### Signed bias attributes

Luma bias and Chroma bias are signed values derived in the server's normalized image
analysis domain. They are not power-ratio attributes. Their primary comparison is a
signed difference rather than a dB quality score. Exact server-side units/definition
must remain versioned metadata because final GPU-side confirmation is still required.

## 6. Remote IQA analysis domain

The GPU service analyzes RGB-family inputs such as PNG/JPEG/BMP. Pair dimensions
must match; dimension mismatch is a failed evaluation rather than an implicit
resize/alignment contract between the pair.

For performance, a 4K-class input is downscaled to an approximately 2K analysis
domain before the IQA feature maps are produced. Structural maps, attribute maps,
weighting, and grid statistics are therefore defined in the remote analysis domain,
not in the original PixelScope source coordinate system.

The server must return enough preprocessing geometry to map results back to the
original image:

- original source width/height;
- analysis width/height;
- source-to-analysis transform or equivalent resize/crop description;
- valid analysis rectangle;
- block/grid origin;
- block dimensions;
- grid width/height;
- border-discard policy/version.

PixelScope must not assume a fixed `0.5` scale. Grid overlay mapping is:

```text
remote grid cell
→ remote analysis coordinate
→ inverse preprocessing transform
→ original source coordinate
→ existing viewer transform
→ screen
```

The server adjusts the block offset and discards incomplete boundary regions rather
than defining partial edge blocks.

## 7. Statistics and aggregation

The server currently uses weighted mean and weighted standard deviation. Weighted
population standard deviation follows:

```text
sqrt(sum(w * (x - mean)^2) / sum(w))
```

Noise receives stronger weighting in flat regions; detail receives stronger
weighting in texture regions; Edge strength receives stronger edge weighting.
Contrast and bias do not use the same region weighting requirement. Exact soft/hard
weighting behavior belongs to the server profile/configuration and must be recorded
as provenance.

A compact block result should expose source-local weighted block statistics rather
than only pairwise ratios. At minimum the current grid contract exposes weighted mean
attribute values. Where the server/result writer can provide sufficient statistics,
prefer:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
```

because adjacent blocks/ROIs can then be aggregated in linear space without averaging
already-aggregated ratios.

The server exposes two official comparison summaries for power attributes:

1. **Ratio of weighted means** — compute source aggregate weighted means first, then
   take the log ratio.
2. **Mean of grid log-ratios** — compute the log ratio for each valid grid block,
   then average those block comparisons.

Both are valid but semantically different. The result artifact and UI must identify
which aggregation is being displayed. PixelScope may recompute derived views from
raw/compact data, but server-authored official statistics remain distinguishable from
PixelScope-derived statistics.

## 8. Result artifact tiers

P5 uses a tiered result contract so large datasets do not require transferring every
2K pixel map to every client.

### Tier 1 — durable job summary

Loaded immediately when a result is opened:

- immutable job/result identity;
- source/scene inventory;
- attribute definitions;
- algorithm/preprocessing/model versions;
- weighting configuration/provenance;
- source identity and hashes;
- official per-scene/per-attribute summary statistics;
- both official aggregation modes where applicable;
- references to compact scene artifacts and optional detail artifacts.

### Tier 2 — compact scene spatial data

Loaded lazily when a scene/attribute is inspected:

- source-local weighted block means or sufficient statistics;
- signed block values for bias attributes;
- validity/grid geometry;
- enough metadata to derive A/B comparisons locally.

This is the normal spatial-overlay input for P5 v1.

### Tier 3 — optional 2K detail artifacts

Large per-pixel attribute maps, common Edge Map, Texture Gate, representative image,
or other debugging artifacts remain optional/lazy. They should not be required for
the normal overview/trend/grid workflow and should not be downloaded eagerly.

A practical storage shape is:

```text
result/<job-id>/
    manifest.json
    summary.npz
    scenes/
        scene_000001.npz
        scene_000002.npz
        ...
    detail/
        ... optional large artifacts ...
```

JSON carries metadata; numeric matrices use NumPy-friendly binary artifacts rather
than large JSON nested-float arrays.

## 9. Immutable result and history

Completed IQA results are durable and are not deleted automatically under normal
operation. Server-side administrative cleanup may occur for capacity/operations, but
ordinary clients should treat a completed result artifact as immutable.

Result provenance should include, when available:

- job/result ID;
- creation time;
- user/purpose/project metadata slots;
- algorithm/preprocessing/model versions;
- PiDiNet/texture model versions;
- weighting/gating configuration;
- source identities and SHA-256 hashes.

Authentication, identity, permission, and administrator policy are P6 concerns. P5
may carry optional provenance metadata but must not implement the P6 credential or
access-control lifecycle.

Historical result reopen is a first-class P5 workflow. PixelScope should eventually
support `Open IQA Result...` and bounded recent IQA result history. If original source
images are unavailable, result-only overview/trend data should remain usable while
source inspection/overlay becomes unavailable.

## 10. Shared storage abstraction

Client and server can access the same Windows SMB/network storage but may see
different physical paths. The API must not depend on a machine-local `G:\...` path or
server `/home/data/...` path.

Use a logical storage root plus relative path:

```text
storage_root_id = iqadata
relative_path = project42/A/0001.png
```

Example mappings:

```text
PixelScope client: iqadata → G:\IQA
GPU server:        iqadata → /home/data/IQA
```

UNC paths are a client-side mapping alternative. The result response should use the
same logical root/reference abstraction.

Local-only inputs may be staged into shared storage. Staging should avoid exposing a
partially copied file to the server; content-addressed reuse by SHA-256 is preferred
where operationally practical.

## 11. Submission pairing contract

P5 v1 UI supports:

- the current two-image PixelScope pair;
- two-folder batch evaluation.

For folder evaluation, the current server behavior pairs sorted folder contents by
index and fails when counts differ. PixelScope should improve safety by resolving the
same deterministic ordered pair list before submission and showing a Pair Preview.
Count mismatch disables submission. Incorrect semantic matching remains the user's
responsibility, but the actual ordered pairs must be visible.

The desired server request is an explicit Scene manifest rather than two opaque
folders. This prevents client/server sorting drift and makes result identities
stable. The v1 UI remains two-source, while the manifest schema uses `sources[]` so a
future N-source Scene does not require a format redesign.

Batch IQA inputs are feature-local evaluation references. A large batch must not be
implicitly registered/Selected/decoded in PixelScope.

## 12. Job API target

The existing server currently supports a blocking HTTP request that returns a result
file location after completion. P5 targets an asynchronous job contract that can be
added to the external server:

```text
POST /v1/iqa/jobs
    → job_id

GET /v1/iqa/jobs/{job_id}
    → queued / preparing / extracting / aggregating / writing /
      succeeded / failed / cancelled
    → completed_sources / total_sources where available

GET /v1/iqa/jobs/{job_id}/result
    → logical result artifact reference

POST /v1/iqa/jobs/{job_id}/cancel
```

Polling is the P5 v1 default. WebSocket progress is not required initially. The
transport adapter must be separable from result parsing so existing/blocking server
interfaces can be bridged without coupling UI/domain code to one endpoint shape.

Typical 4K-class source extraction is approximately two seconds per source, so batch
jobs must be non-modal and cancellable while ordinary PixelScope work continues.

## 13. UX contract

P5 should add one non-modal **IQA workspace/dock** rather than making a large custom
modal dialog the primary workflow.

Conceptual dock states/tabs:

```text
IQA
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
│   ├─ Running
│   ├─ Completed
│   └─ Failed
└─ Results
    ├─ Overview
    ├─ Attribute trend/outliers
    └─ Scene inspection controls
```

Native OS file/folder pickers may remain modal. Pair preview, job execution, and
result exploration remain non-modal.

### Quick current-pair workflow

When exactly two eligible native sources are the current comparison pair, IQA Setup
can reuse them directly. The user should not have to browse to the same files again.

### Batch workflow

Folder A / Folder B are selected in IQA Setup, the deterministic ordered pair list is
shown, and the batch is submitted without altering the user's current Files/Selected
workspace.

### Result hierarchy

Results follow:

```text
Job / dataset
    ↓
10-attribute overview
    ↓
selected attribute trend / outliers
    ↓
selected scene
    ↓
spatial grid comparison
    ↓
block inspector
```

The overview may use an Attribute × Scene matrix plus a selected-attribute trend.
The two official aggregation modes must be selectable and clearly labeled.

### Passive browsing versus inspection

Selecting an IQA result row/scene should not mutate PixelScope Selected state.
`Inspect Pair` (or an equivalent explicit command) registers/selects only the chosen
scene's sources through the inherited canonical PixelScope path and links scene
navigation to the viewer.

Inspection should keep IQA Reference separate from PixelScope Primary. A transient
`Return to previous workspace` context may restore the pre-inspection comparison
workspace; it is not Session persistence.

Temporary P4-A Picks and IQA Inspect Selected mutation must not conflict silently.
P5 v1 should prevent entering Inspect while an active temporary curation baseline
would be invalidated, unless a later explicit policy is designed.

## 14. Test/sample contract

P5 runtime development starts from a deterministic synthetic server/result fixture,
not from the live GPU service.

The P5-A sample generator must create a small production-shaped result with roughly
10–12 scenes × 2 sources and all ten attributes. Data is intentionally structured,
not random-only, so tests can assert the complete drill-down workflow.

The fixture should include:

- clear attribute trends and at least one spatial outlier;
- positive, negative, and near-zero directional comparisons;
- signed Luma/Chroma bias crossing negative/zero/positive values;
- two official aggregation modes that intentionally produce different results in at
  least one scene;
- source-local weighted block means/sufficient statistics whose local recomputation
  matches official fixture statistics;
- default 32/128 block profiles plus a variant attribute/profile proving the client
  does not hard-code those values;
- non-zero grid origin and discarded border geometry;
- source→analysis transform metadata;
- soft-weight profile metadata and a hard-gate profile variant;
- identical-source comparison case;
- near-zero power handling;
- dimension-mismatch rejection fixture;
- missing/corrupt compact scene artifact behavior;
- optional detail artifact absent/present cases.

Large real 2K pixel arrays are not required in repository fixtures. Detail-map tests
may use a smaller synthetic analysis domain while preserving production metadata and
lazy-load semantics.

## 15. Explicit P5 boundaries

P5 does not own:

- external GPU model implementation/training code;
- login/SSO/token/permission/admin lifecycle (P6);
- arbitrary server retention administration;
- local RAW demosaic/WB/CCM/tone-map processing;
- source-residency or preload redesign;
- Difference numerical redesign;
- Saved ROI/Overlay deferred from P4;
- packaging/signing/update strategy (P7).

P5 may request new server interfaces and result writers, but those changes are
implemented and versioned in the external IQA server repository.