# Execution plan: P5 — Remote IQA Platform

Status: Active — P5-A2 Stage 2 executable-v2 migration / PR #40; P5-B schema-dependent/paused
Owner: repository owner + P5 orchestrator + slice implementation/review agents
Last updated: 2026-08-21
Inherited merged baseline: P5-A2 Stage 1 / PR #39 / main
`4f2d58f36152cbebd1110a2aed09afacc6f09596`

Authoritative P5 documents:

- product/architecture contract:
  [`docs/REMOTE_IQA_CONTRACT.md`](../../REMOTE_IQA_CONTRACT.md)
- current numerical/result target:
  [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)
- historical merged schema-v1 baseline:
  [`docs/REMOTE_IQA_V1_SPEC.md`](../../REMOTE_IQA_V1_SPEC.md)
- active schema-v2 revision note:
  [`docs/exec-plans/active/p5-schema-v2-revision.md`](p5-schema-v2-revision.md)
- completed P4 plan:
  [`docs/exec-plans/completed/p4-workflow-session-productivity.md`](../completed/p4-workflow-session-productivity.md)

## Program-governance model

P5 is run as an orchestrated multi-PR program.

- **P5 orchestrator** owns this execution plan, durable cross-slice contracts, scope
  boundaries, owner-decision tracking, and evaluation of implementation/review
  evidence. Missing product/algorithm policy is resolved with the repository owner
  before dependent implementation proceeds.
- **Slice implementation agents** implement only their named slice against latest
  `main` plus durable P5 documents. They do not redefine cross-phase contracts in UI
  or transport code.
- **Independent review agents** review the latest full PR head against ROADMAP/P5
  contracts, inherited P2/P3/P4 authorities, tests, resource/lifetime behavior, and
  durable docs. They do not directly modify code/docs.
- **Repository owner** supplies unresolved product/server-policy decisions and runs
  requested local Windows validation for runtime/UI slices.

When implementation exposes a missing cross-slice decision, it stops at the existing
contract boundary. The orchestrator/owner updates durable docs before dependent code
continues. PR #39 demonstrated this governance rule: P5-B exposed a schema issue, so
the schema contract was corrected on `main` before the executable Stage-2 migration
and before P5-B resumes.

## Goal

P5 connects PixelScope to an external GPU Image Quality Assessment service while
preserving PixelScope as a fast local comparison tool.

The intended user flow is:

1. inspect images rapidly with existing PixelScope tools;
2. submit a deterministic current or batch IQA evaluation;
3. continue ordinary local work while a remote job runs;
4. reopen immutable historical IQA results without rerunning the GPU job;
5. browse absolute/relative dataset and Scene trends;
6. switch IQA Reference across N-way comparison variants;
7. drill down to spatial grids and explicitly connect interesting Scenes to the
   existing PixelScope viewer.

GPU model/server implementation remains in its external repository. PixelScope owns
client preparation, stable result parsing, local derived exploration, result history,
and viewer integration.

## Inherited P2/P3/P4 authority

The sole local image/runtime hierarchy remains:

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

`Analysis Working Set = Current Comparison Page`.

P5 must not create another authority for Files/Selected/Current Comparison Page,
source residency/protection/preload/generation, Difference/cache, Display Gain, or
Session v1. Remote batch membership and passive result browsing remain feature-local.

## Current executable schema-v2 target

The merged P5-A/schema-v1 implementation is historical executable compatibility. PR
#39 is the merged durable schema-v2 contract. PR #40 is the active executable Stage-2
migration.

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

### Identity

- `variant_id` = stable comparison-group/configuration across Scenes and the local
  Reference/target slot identity;
- `source_id` = stable concrete-image identity;
- `scene_id` = evaluation Scene;
- `measurement_context_id` = Scene evaluation context governing the published
  weighted measurement.

For a normal non-PARTIAL complete result, each Scene contains exactly one binding for
each declared variant in top-level variant order. One concrete `source_id` may appear
in multiple Scenes or multiple variant slots when the immutable concrete-source
metadata is identical. Variant identity remains `variant_id`; repeated source identity
does not imply reuse of weighted measurements.

Comparable variants in one Scene/attribute carry **exactly equal** source-to-analysis
and grid geometry metadata. Equal original dimensions/no client alignment remain
required.

"Absolute" means reference-independent inside the published Scene context. A weighted
measurement is not globally reusable across incompatible Scene contexts solely because
a source ID or hash matches.

### Server measurement authority

For every source/attribute/grid, schema v2 retains:

```text
weight_sum
weighted_sum
weighted_square_sum
valid_count
valid_mask
```

The canonical Scene absolute mean is `ΣS1/ΣW`; matching weighted population std is
recomposed from W/S1/S2.

Small Scene/dataset summaries are server-authored fast projections. W/S1/S2/count/
valid + normative formulas remain authority; projection mismatch beyond the v2
specified tolerance is corrupt.

### Dataset absolute summary

The schema publishes both:

- pooled weighted measurement mean/std across Scenes;
- equal-Scene mean/std over canonical Scene means.

**Owner-selected default absolute Dataset Overview: `pooled_weighted_mean`.**

### Local reference comparison

Pair-valid support is the target/reference valid-grid intersection on validated common
physical grid topology.

Power modes:

1. ratio of pair-valid aggregate weighted means;
2. unweighted arithmetic mean of **finite** pair-valid grid log-ratios.

For mode 2, an undefined/non-finite per-cell ratio such as epsilon-zero `0/0` does not
invalidate a Scene when another pair-valid cell has a finite dB value; only finite
cell dB values enter the arithmetic mean. If none remain, the mode is invalid.
Negative power-domain input remains invalid rather than skippable.

Signed mode: pair-valid weighted target mean minus pair-valid weighted reference mean.

The Qt-free v2 comparison layer also owns quality orientation for both power modes:
higher-is-better keeps raw sign, lower-is-better negates raw sign, and signed/neutral
attributes expose no quality delta.

**Owner-selected default relative Dataset Overview:** compute the selected comparison
independently for each valid Scene, then arithmetic-mean the valid Scene comparison
values. This rule applies to both power modes and signed deltas.

### Artifact purpose and summary-first filesystem boundary

1. **Summary metadata** — small open-time absolute Dataset/Scene summaries.
2. **Grid measurement artifacts** — primary analytical data for local reference
   comparisons and spatial views.
3. **Optional detail artifacts** — opaque bounded references in Stage 2; typed detail
   decode semantics are deferred.

Ordinary schema-v2 open performs filesystem I/O for `manifest.json` and `summary.npz`
only. Scene-grid/detail path syntax is validated without touching those files. Scene
grid existence/containment/archive/array validation occurs on `load_grid_scene()`.
Actual grid loading/batching/cache remains a bounded, non-blocking client policy for
P5-B/P5-F.

### Safety envelope

The Stage-2 executable parser freezes bounded manifest/NPZ/cardinality input. The
aggregate `1024` Scene-source-binding ceiling is deliberate: Stage-1 planning assumed
roughly 300 compared source images, so it provides more than 3x headroom and still
permits all 512 Scenes for the initial two-variant P5-C workflow. It is an acceptance
safety envelope, not a cache budget. Larger production requirements require an
explicit coordinated schema/safety review rather than a silent local override.

### v1 compatibility

- v2 becomes current/default after executable migration;
- v1 stays explicit read-only historical compatibility;
- no silent v1→v2 upgrade invents absolute source measurements;
- v1 UI remains limited to data actually available in v1;
- new writers/fixtures target v2 after migration.

### PARTIAL direction

Durable PARTIAL results remain owner-approved and successful Scene work must be
preservable. Stage 2 explicitly returns `UNSUPPORTED` for v2 PARTIAL because P5-C
owns the detailed missing-variant/failure/terminal/publication/cancel semantics.

## Geometry/input baseline carried forward

The continuous pixel-edge coordinate system, half-open cells/valid rectangles,
source→analysis affine direction, and continuous inverse mapping proven in P5-A remain
the geometry baseline unless a later explicit schema changes them.

The current remote input baseline remains PNG/JPG/JPEG/BMP with no silent RAW
conversion. Current Pair/folder formation remains deterministic and independent from
Primary/Active/viewer reorder.

P5-C request/result identity remains N-way-capable through explicit ordered Scene
manifests, but **the initial P5-C submission UI remains two-variant only**: Current
Pair and deterministic two-folder Pair. Arbitrary three-or-more-variant submission UI
is deferred and requires a later explicit owner decision. This does not limit P5-B
N-way result exploration or Reference switching.

## UX direction

P5 adds one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

Results browse:

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

Passive browsing never mutates Selected. Explicit Inspect uses canonical local
registration/selection only for chosen Scene sources. IQA Reference is separate from
Primary. P4-A temporary Picks block conflicting Inspect entry. Return-to-previous-
workspace remains transient and invalidates rather than overwriting newer non-IQA
intent.

## Program sequence

`P5-0 → P5-A(v1) → P5-A2(v2 migration) → P5-B → P5-C → P5-D → P5-E → P5-F → P5 Complete`

| Order | Slice | Status |
|---|---|---|
| 0 | P5-0 P4 Closure & P5 Program Setup | Complete — PR #36 |
| 1 | P5-A Contract Fixtures & IQA Domain / schema v1 | Complete — PR #37 |
| 2 | P5-A2 Schema v2 migration | **Active — Stage 1 PR #39 merged; Stage 2 executable migration PR #40 Draft** |
| 3 | P5-B IQA Workspace & Local Result Exploration | Paused — schema-dependent until P5-A2 Stage 2 merges |
| 4 | P5-C Submission & Shared Storage | Planned — C1 + detailed C2 gates pending; PARTIAL allowed |
| 5 | P5-D Viewer-linked Scene Inspection | Planned |
| 6 | P5-E Historical Result Workflow | Planned |
| 7 | P5-F Integration & Performance Hardening | Planned |

## P5-0 — P4 Closure & P5 Program Setup — Complete

P5-0 closed P4, established the broad Remote IQA product contract, froze the original
schema-v1 numerical/parser/geometry rules for P5-A, and created P5-C decision gates.

## P5-A — Contract Fixtures & IQA Domain / schema v1 — Complete

P5-A merged as PR #37 at
`fceb16f6e43c48ec65fbf7ebbcc103b56716b686`.

It delivered a Qt-free schema-v1 domain/parser, deterministic production-shaped
fixtures, W/S1/S2/count/valid recomposition, two pairwise power modes, explicit
invalid/corrupt/unsupported results, safe bounded NumPy parsing, and exact continuous
source/analysis geometry. It remains valuable historical executable compatibility,
but its server-authored pairwise result model is no longer the current target.

## P5-A2 — Schema v2 migration — Active

### Stage 1 — durable contract revision / PR #39 — Complete

PR #39 merged at `4f2d58f36152cbebd1110a2aed09afacc6f09596` and froze:

- Scene-context meaning of absolute measurement;
- `variant_id` / `source_id` / `measurement_context_id` identities;
- normal complete-result variant cardinality;
- cross-variant physical grid correspondence;
- canonical Scene `ΣS1/ΣW` absolute reduction;
- pooled and equal-Scene dataset absolute summaries;
- default absolute Overview = pooled weighted mean;
- single authority rule for summary projections vs accumulators;
- local pair-valid power/signed comparison semantics;
- default relative Overview = arithmetic mean of valid Scene comparisons;
- v1 read-only compatibility;
- PARTIAL direction carry-forward;
- separation of artifact purpose from loading/cache policy;
- P5 durable system-of-record docs.

PR #39 was docs/schema-contract-only and did not modify P5-B runtime/UI code.

### Stage 2 — focused executable-v2 domain/fixture/parser migration — Active / PR #40

This must land on `main` **before P5-B resumes**.

PR #40 implements and freezes:

- versioned v2 domain/manifest/summary/grid models;
- concrete JSON/NPZ field placement and dtype/shape constraints;
- bounded and justified v2 safety ceilings;
- `measurement_context_id` construction/fingerprint rules;
- complete-result variant/cardinality/exact-grid-correspondence validation;
- reusable concrete `source_id` with immutable metadata equality, including
  identical-source multi-variant bindings;
- summary projection consistency tolerance validation;
- v2-owned finite-grid Mode-2 reduction, Mode-1, signed, and quality-orientation
  helpers;
- deterministic N-way and hand-calculated goldens plus corruption/limit regressions;
- explicit v1 read-only compatibility dispatch;
- safe corruption/future-version behavior;
- summary-first filesystem boundary and opaque detail references;
- explicit Stage-2 `UNSUPPORTED` handling for PARTIAL.

Current remaining closure gates are repository-pinned validation and fresh independent
latest-head review. No P5-B UI policy is introduced in this stage.

## P5-B — IQA Workspace & Local Result Exploration — Paused

PR #38 is schema-dependent work in progress. It must not be merged/review-closed on the
old schema after PR #39 establishes v2.

After P5-A2 Stage 2 merges:

1. rebase P5-B onto latest `main`;
2. consume the executable v2 Open Result/domain path;
3. support N-way `variant_id` Reference selection;
4. show fast absolute summary-based Overview and Scene Trend;
5. default absolute Dataset Overview to `pooled_weighted_mean`;
6. derive requested target/reference values locally from grid measurements using the
   canonical raw/quality comparison helpers;
7. default relative Overview to arithmetic mean of valid Scene comparisons;
8. keep grid I/O/numerical work outside the Qt UI thread;
9. expose bounded Loading/Calculating state and reject stale callbacks;
10. preserve Files/Selected/native-analysis state during passive browsing;
11. retain close/recreate safety.

P5-B does not open historical source pixels directly and does not create another
source/path authority.

## P5-C — Submission & Shared Storage — Planned

### Goal

Connect the proven v2 artifact/result path to the external GPU service.

### Owner-decision gates

#### Gate C1 — logical storage-root configuration ownership

Choose one machine-local authority for:

```text
storage_root_id → client path / UNC path
```

Preferred candidate remains typed `ApplicationSettings` with explicit schema migration
if it fits. Result artifacts and Session cannot own machine-local mappings.

#### Gate C2 — PARTIAL allowed; detailed terminal contract pending

The central policy is fixed: durable PARTIAL results are allowed and successful Scene
outputs must be preservable. Before transport implementation, freeze:

- request-level validation/rejection;
- per-Scene failure record schema/reasons;
- missing-variant semantics;
- exact PARTIAL API/terminal identity;
- required artifacts for successful/failed Scenes;
- behavior when no Scene succeeds;
- cancel/completion/publication races.

### Submission cardinality — owner decision

The schema/request identity is N-way-capable, but the initial P5-C user-facing submit
workflow is deliberately limited to **two variants**:

- Current Pair = exactly two variants;
- batch = deterministic two-folder Pair;
- arbitrary N-way submission UI is deferred to a later explicit owner decision;
- P5-B remains N-way-capable for opening/exploring externally produced v2 results.

### Scope after gates close

- logical storage-root mapping and safe shared staging;
- deterministic two-variant Current Pair and two-folder Pair submission;
- explicit ordered Scene manifest request whose identity model remains N-way-capable;
- HTTP submit/status/result/cancel adapter, polling first;
- non-modal Jobs progress;
- handoff into the exact P5-B canonical Open Result path;
- retry/failure/cancel under finalized C2;
- no batch Files/Selected/residency authority.

Server implementation remains outside this repository.

## P5-D — Viewer-linked Scene Inspection — Planned

### Goal

Connect result anomalies to existing source-image viewing without a new source or
local-analysis authority.

### Scope

- explicit Inspect and P4-A Pick guard;
- canonical registration/selection of inspected Scene sources only;
- transient return snapshot and stale-intent invalidation;
- IQA Reference independent from Primary;
- linked Scene navigation;
- exact grid→analysis→source→viewer mapping;
- vector/grid overlay from schema-v2 absolute/relative measurements;
- block inspector with source values/comparison/quality/geometry;
- missing/hash-mismatch source degradation;
- no Difference/ROI/Line/Display-Gain semantic changes.

## P5-E — Historical Result Workflow — Planned

### Goal

Make completed remote results durable reusable engineering records.

### Scope

- extend the P5-B canonical Open Result path; do not introduce another one;
- bounded Recent IQA Results;
- production logical-root reopen;
- immutable job/result identity and source hashes;
- result-only mode when sources are unavailable;
- source/hash mismatch diagnostics;
- provenance presentation;
- explicit v1 read-only historical compatibility;
- history references result identity/path, not copied arrays in Session.

P5 does not modify Session v1. Authentication/SSO/token/permission/admin operations
remain P6.

## P5-F — Integration & Performance Hardening — Planned

### Goal

Validate real-server and realistic-dataset composition while preserving inherited
local authority/lifecycle contracts.

### Scope

- real server compatibility against current schema v2;
- v1 read-only historical compatibility;
- bounded grid loading/cache characterization;
- SMB/network bandwidth and local reference-switch latency;
- current-pair/two-folder submission stress plus N-way result/parser/Reference stress;
- cancellation/failure/missing-artifact/application close-recreate;
- no batch-driven Files/Selected/residency/preload authority;
- polling/task teardown and stale-result rejection;
- optional detail characterization;
- durable P5 closure docs.

No wall-clock threshold is a correctness merge gate. Deterministic gates are correct
identity/math/geometry, bounded ownership/loading, no duplicate work, stale callback
rejection, and teardown safety.

## Review workflow for every runtime slice

1. orchestrator confirms latest `main`, previous P5 merges, and unresolved owner gates;
2. implementation agent receives a slice-specific prompt derived from this plan;
3. implementation stays within that slice and commits intentional subunits;
4. owner runs requested focused Windows validation;
5. implementation agent opens/updates the PR with goals, contract preservation, test
   evidence, exclusions, and ChatGPT co-author attribution where agent-generated;
6. independent reviewer checks latest full head against ROADMAP/P5 specs/inherited
   architecture, tests, resource/lifetime behavior, and docs;
7. orchestrator classifies findings as implementation defect, missing contract, or
   owner-decision request;
8. implementation fixes defects; orchestrator/owner resolves contract decisions before
   dependent code continues;
9. latest head is re-reviewed when blockers were found;
10. only then does the orchestrator recommend merge and prepare the next slice.
