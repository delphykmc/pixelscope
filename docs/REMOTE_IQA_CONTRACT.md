# Remote IQA contract

Status: P5 planning contract
Owner: PixelScope P5 program + external IQA server contract
Established: P5-0

This document defines the stable product/architecture boundary for PixelScope P5.
The external GPU IQA implementation lives in a separate repository. PixelScope
consumes a versioned job/result contract and does not reimplement the server's signal
extraction models.

**Normative P5 v1 numerical, identity, coordinate, parser, and publication semantics
are defined in [`REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).** Where this broader
contract leaves an implementation detail open, that v1 specification controls. P5-A
implementation and golden tests must satisfy both documents.

## 1. Product goal

P5 lets a user:

1. inspect images quickly with existing local PixelScope comparison tools;
2. submit the current pair or a large two-folder evaluation to the GPU IQA service;
3. continue normal PixelScope work while a remote job runs;
4. reopen durable historical results instead of rerunning the GPU job;
5. explore `dataset → attribute → scene → spatial block`;
6. explicitly inspect selected IQA scenes in the existing viewer.

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

## 3. Scene-based remote authority

The remote model is:

```text
IQA Job
    ↓
Scene
    ├─ Source 0 / Source 1 / future Source N
    ├─ representative image
    ├─ common Edge Map
    ├─ common Texture Gate
    └─ per-source attribute results
          ↓
     derived comparisons
```

A Scene is the unit sharing common structural context. P5 v1 UI is two-source, while
the durable schema is N-source-ready with stable `scene_id`, `source_id`, ordered
`sources[]`, and comparison operand IDs.

The common Edge Map is produced from the representative image using PiDiNet. The
Texture Gate comes from the server texture network. Both are continuous 2K-analysis-
domain maps and are scene-common. The server may use soft weights, hard gates, or
thresholds. PixelScope must not reverse-engineer effective numerical weighting from
these visualization maps.

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

Block sizes are server metadata, not PixelScope constants. Attribute metadata must
carry stable ID/name, value kind, comparison operator, quality direction, units,
block/grid geometry, weighting provenance, and all numerical stabilization metadata
required by the v1 spec.

Directional power attributes compare raw A/B power in dB. Raw sign and user-facing
quality sign are distinct. Noise reverses quality interpretation; higher-is-better
attributes do not. Luma/Chroma bias are signed neutral values and use signed delta,
not power-ratio quality dB. Exact bias unit remains versioned server metadata.

## 5. Remote analysis domain and geometry

The GPU service operates on RGB-family encoded image inputs. P5 v1 remote eligibility
is deliberately narrower than local PixelScope discovery and is frozen by the v1
spec; RAW has no implicit remote conversion path.

All sources in a Scene must have equal original dimensions. For performance, 4K-class
inputs are normally downscaled to approximately 2K before structural/attribute maps
and grid statistics are created.

The result must carry exact original/analysis geometry, source→analysis transform,
valid analysis rectangle, grid origin/dimensions, block size, and border-discard
metadata. PixelScope must never assume a fixed 0.5 scale.

The v1 specification defines a single continuous pixel-edge coordinate convention,
half-open cells/valid rectangles, affine direction, inverse mapping, clipping, and
rounding boundary. P5-A must prove it with a non-integer scale/crop/origin fixture.

## 6. Statistics and recomposition

The server uses weighted mean and weighted population standard deviation. Noise is
weighted toward flat regions, detail toward texture, and Edge strength toward edges;
contrast/bias do not have the same region-weight requirement. Exact soft/hard policy
is server-profile provenance.

P5 v1 compact scene data carries mandatory linear-domain sufficient statistics so
local recomposition is deterministic without full 2K maps. The normative field set,
valid-block rule, zero-weight behavior, and invalid serialization are frozen in the
v1 specification.

The server exposes two distinct official power comparisons:

1. ratio of aggregate weighted means;
2. arithmetic mean of valid per-grid log ratios.

Both remain explicitly labeled. PixelScope-derived values do not overwrite the
identity of server-authored official statistics.

## 7. Tiered durable result

P5 avoids eager full-map transfer:

1. **Tier 1 — Job summary:** immutable manifest, source/scene/attribute inventory,
   provenance, official summaries, and artifact references.
2. **Tier 2 — Compact scene data:** mandatory block sufficient statistics and grid
   validity/geometry, loaded lazily for inspected scenes.
3. **Tier 3 — Optional detail:** per-pixel 2K attributes, common Edge Map, Texture
   Gate, representative image, and debugging artifacts, loaded only when requested.

Conceptual layout:

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

Top-level result kind/schema, safe relative-path resolution, safe NumPy loading,
shape/dtype/size bounds, N-source structure, and immutable publication semantics are
normative in the v1 specification.

Published results are historical engineering artifacts. Ordinary clients treat them
as immutable and expect them to persist until explicit/administrative deletion.
Authentication/identity/permission/admin lifecycle remains P6; P5 may display server-
supplied provenance such as user/purpose/project.

## 8. Shared storage abstraction

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

The machine-local configuration owner for logical-root→client-path mapping is an
explicit **P5-C owner decision gate**. Result artifacts and Session cannot own it.

## 9. Submission pairing

P5 v1 supports:

- Current Pair from an already-open deterministic two-source page;
- two-folder batch evaluation.

Current Pair A/B identity and the exact folder discovery/sort/pair algorithm are
normative in the v1 specification and must not depend on Primary/Active/viewer reorder
or on server re-sorting.

Folder Pair shows the complete ordered Pair Preview and blocks count mismatch before
submit. Incorrect semantic same-index matching remains the user's responsibility.
The request is an explicit Scene manifest with `sources[]`; large batch references do
not become Files/Selected/decoded source ownership.

Batch failure granularity (whole-job failure versus durable partial Scene results and
cancel/completion races) is an explicit **P5-C owner decision gate** and must be frozen
before transport implementation.

## 10. Job API target

The existing service has a blocking HTTP interface. P5 targets a separable async job
adapter:

```text
POST /v1/iqa/jobs              → job_id
GET  /v1/iqa/jobs/{job_id}     → progress/state
GET  /v1/iqa/jobs/{job_id}/result → logical result reference
POST /v1/iqa/jobs/{job_id}/cancel
```

Polling is v1 default; WebSocket is not required. Typical 4K extraction is about two
seconds per source, so batch work is non-modal and cancellable. A result is not
`succeeded`/historically openable until the v1 publication contract is complete.

## 11. UX contract

P5 adds one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
└─ Results
```

Native OS file/folder pickers may remain modal; pairing, jobs, and result exploration
remain non-modal.

Results drill down:

```text
Job / dataset
    ↓
10-attribute overview
    ↓
attribute trend / outliers
    ↓
Scene
    ↓
spatial grid comparison
    ↓
block inspector
```

Passive result browsing never changes Selected. Explicit **Inspect Pair** loads only
the chosen Scene pair through the canonical local registration/selection path. IQA
Reference is independent from Primary.

P5 v1 blocks Inspect while a P4-A temporary Pick baseline is active. Return-to-previous-
workspace is transient, not Session persistence, and its invalidation behavior is
normative in the v1 specification so it cannot overwrite newer non-IQA workspace
intent.

## 12. Open Result ownership

P5-B establishes the one canonical `Open IQA Result...` parser/controller path against
fixture/local artifacts. P5-E extends that same path with production logical-storage
reopen, bounded Recent IQA Results, provenance, source/hash diagnostics, and result-
only mode. P5-E does not create a second Open Result authority.

If original images disappear, Tier-1 overview/trends remain usable while source-linked
inspection/overlay is unavailable.

## 13. Fixture-first implementation

P5-A starts without a live GPU server. A deterministic production-shaped fixture must
cover roughly 10–12 two-source Scenes × all ten attributes with intentional trends,
outliers, signed bias, near-zero values, differing official aggregation modes, dynamic
grid size, nontrivial geometry, weighting provenance, mismatch/corruption, and optional
detail capabilities.

The v1 specification additionally requires golden tests for epsilon, exact A/B signs,
valid-grid intersection, mandatory sufficient-statistic recomposition, invalid/null
behavior, non-integer coordinate inversion, unsafe artifact rejection, incomplete
publication, and at least one small 3-source structural case.

Large real 2K arrays are not repository fixture requirements.

## 14. Explicit P5 boundaries

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