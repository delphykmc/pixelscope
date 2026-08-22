# Completed execution note: P5 IQA schema v2 source-measurement revision

Status: Complete — P5-A2 Stage 1 / PR #39 and Stage 2 / PR #40 merged
Owner: repository owner + P5 orchestrator
Stage-2 base: `main@4f2d58f36152cbebd1110a2aed09afacc6f09596` (PR #39 merge)
Stage-2 merge: `5fcea48bd80e7a9aa5f5caa42fdaabebb27256d6` (PR #40)
Current schema authority: [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)
Historical executable baseline: P5-A / PR #37 / schema v1

This file preserves the rationale and closure record for the schema-v2 interruption
that preceded P5-B. It is no longer an active execution plan. P5-B subsequently
rebased/reworked and merged as PR #38; P5-C is the current active slice.

## Why P5-A2 existed

P5-A/schema v1 proved versioned result parsing, bounded NPZ input, geometry,
sufficient statistics, and deterministic fixtures. P5-B design then exposed that a
pairwise-centered stored result did not scale cleanly to N-way A/B/C/D-style variants
with a freely switchable IQA Reference.

PR #39 therefore froze the durable schema-v2 ownership model first. PR #40 then
implemented the versioned Python domain, deterministic fixture, parser/reader,
numerical helpers, safety validation, tests, and concrete artifact contract before
P5-B resumed.

## Governing ownership

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Server authority includes source decoding, IQA extraction, Scene-context
weighting/gating, validity, physical geometry, W/S1/S2/count/valid, absolute summaries,
and provenance.

PixelScope authority includes `variant_id` Reference selection, local target/reference
comparison, Dataset/Scene reductions, quality-direction presentation, spatial derived
values, and bounded asynchronous result-grid loading policy.

PixelScope does not recompute IQA from source pixels, reconstruct server weighting, or
align/resize incompatible published grids.

## Stage-2 executable decisions frozen by PR #40

PR #40 established:

- canonical dispatcher: v2 → v2 reader, v1 → historical read-only reader, future →
  `UNSUPPORTED`;
- no synthetic v1→v2 upgrade;
- N-way ordered `variant_id` identity separated from concrete `source_id`;
- repeated `source_id` acceptance only with identical immutable source metadata;
- every COMPLETE Scene binding every declared variant exactly once in top-level
  variant order;
- deterministic Scene-context-scoped `measurement_context_id`;
- exact cross-variant SceneGeometry and per-attribute GridGeometry equality;
- reference-neutral v2 operators;
- one Qt-free comparison authority returning raw engineering orientation and
  user-facing quality orientation;
- finite-only Mode-2 per-grid dB reduction with explicit no-finite-ratio behavior;
- summary-first ordinary result open, with Scene-grid/detail access deferred;
- opaque bounded `detail_artifacts` pending a later typed P5-D contract;
- aggregate 1024 Scene-source-binding parser acceptance ceiling as a deliberate
  safety envelope rather than a cache budget.

At the Stage-2 boundary, PARTIAL was intentionally deferred until P5-C. P5-C later
froze and implemented ordered `scene_outcomes[]` while retaining `schema_version = 2`.
The current PARTIAL rules live only in `REMOTE_IQA_V2_SPEC.md`; this completed plan is
historical context, not the current PARTIAL authority.

## Numerical hierarchy established

### Absolute Scene

For valid cells:

```text
scene_W  = sum(W)
scene_S1 = sum(S1)
scene_S2 = sum(S2)
scene_mean = scene_S1 / scene_W
```

Population std derives from W/S1/S2. Equal-grid arithmetic mean is not the canonical
Scene mean.

### Absolute Dataset

Both reductions remain explicit:

1. pooled W/S1/S2 measurement statistics;
2. equal-Scene mean/std across valid canonical Scene means.

Default absolute Dataset Overview is pooled weighted mean.

### Relative Scene

Pair-valid support is target-valid AND reference-valid on a validated common grid.

- power mode 1: ratio of pair-valid aggregate weighted means;
- power mode 2: unweighted arithmetic mean of finite pair-valid grid log-ratios;
- signed: pair-valid weighted target mean minus reference mean.

### Relative Dataset

Default relative Dataset Overview is the arithmetic mean of valid per-Scene selected
comparison values. This equal-Scene rule applies to both power modes and signed delta.

## Concrete artifact boundary

```text
result/
    manifest.json
    summary.npz
    scenes/<scene_id>.npz
    detail/...                 optional opaque references
```

`summary.npz` contains Scene absolute data with axes `(scene, variant, attribute)` and
Dataset absolute data with axes `(variant, attribute)`. Scene grids contain identity
arrays plus per-attribute W/S1/S2/count/valid arrays with axes `(variant, row, column)`.

Exact current field/dtype/shape/safety/PARTIAL rules are maintained in
`REMOTE_IQA_V2_SPEC.md`.

## Review findings closed during Stage 2

Independent/orchestrator review drove these important closure changes:

1. Mode-2 finite reduction no longer inherited v1 fail-fast per-cell ratio behavior.
2. Same concrete source may occupy multiple variant slots when immutable source
   metadata is identical; `variant_id` remains the slot identity.
3. Durable system-of-record docs were reconciled with executable v2.
4. The 1024 aggregate source-binding cap was documented as an explicit parser safety
   envelope relative to the then-planned production cardinality.

Repository-native Stage-2 tests were distributed across:

```text
tests/unit/test_remote_iqa_v2.py
tests/unit/test_remote_iqa_v2_limits.py
tests/unit/test_remote_iqa_v2_review_regressions.py
```

The real schema-v1 golden remained exercised through canonical dispatch rather than
being synthesized or rewritten.

## Historical Stage-2 validation gate

The Stage-2 merge process required focused v1/v2 tests followed by docs, Ruff, mypy,
pip, full pytest, and diff checks. Only commands actually observed were recorded as
PASS. Those historical results remain evidence for PR #40 only and are not validation
for later P5-B/P5-C heads.

## What later slices inherited

P5-B inherited the executable v2 reader/math and implemented the canonical local
Results workspace. P5-C inherited that same result authority and added machine-local
logical storage configuration, deterministic two-variant submission, Jobs transport,
executable PARTIAL results, and explicit Open Result delegation back to P5-B.

P5-D owns typed spatial/detail consumption and source Inspect. P5-F owns measured real
server/shared-storage performance and cache/preload tuning. A future production
requirement beyond the current parser safety ceilings requires an explicit schema/
safety review rather than a local bypass.
