# Execution note: P5 IQA schema v2 source-measurement revision

Status: Active — P5-A2 Stage 2 executable migration in PR #40
Owner: repository owner + P5 orchestrator
Stage-2 base: `main@4f2d58f36152cbebd1110a2aed09afacc6f09596` (PR #39 merged)
Schema authority: [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)
Historical executable baseline: P5-A / PR #37 / schema v1
Schema-dependent paused work: P5-B / PR #38

## Why Stage 2 exists

P5-A/schema v1 proved versioned result parsing, bounded NPZ input, geometry, sufficient
statistics, and deterministic fixtures. P5-B then exposed that a pairwise-centered
stored result does not scale cleanly to N-way A/B/C/D-style variants with a freely
switchable IQA Reference.

PR #39 therefore froze the durable schema-v2 ownership model first. PR #40 is the
focused executable migration that turns that contract into versioned Python domain,
fixture, parser/reader, numerical helpers, safety validation, tests, and concrete
artifact documentation before P5-B is allowed to rebase.

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

## Stage-2 executable decisions frozen in PR #40

The current branch makes the following concrete v2 choices normative:

- canonical dispatcher: v2 -> v2 reader, v1 -> historical read-only reader, future ->
  `UNSUPPORTED`;
- no synthetic v1-to-v2 upgrade;
- N-way top-level ordered `variant_id` identity separated from concrete `source_id`;
- `source_id` may recur across different Scenes only when immutable source metadata is
  identical;
- duplicate `source_id` binding inside one complete Scene is forbidden;
- weighted measurement identity remains Scene-context scoped by deterministic
  `measurement_context_id`;
- context format is `mc2:<sha256>` over canonical JSON with `float.hex()` geometry
  tokens;
- complete Scenes contain exactly one source per declared variant in exact variant
  order;
- original dimensions match across Scene variants;
- duplicated SceneGeometry and per-attribute GridGeometry are required to compare
  exactly equal across Scene variants;
- v2 operator names are reference-neutral:
  `power_ratio_target_over_reference_db` and `signed_target_minus_reference`;
- one Qt-free v2 comparison authority returns both raw engineering orientation and
  user-facing quality orientation;
- higher-is-better power uses `quality = raw`, lower-is-better uses `quality = -raw`
  for both power modes, and signed/neutral quality is N/A;
- ordinary result open touches only `manifest.json` and `summary.npz`; deferred grid/
  detail references receive syntax-only path validation at open and filesystem access
  is deferred to the requested artifact;
- optional `detail_artifacts` are opaque bounded references in Stage 2, not a frozen
  P5-D decode schema;
- `publication_state=partial` is explicitly `UNSUPPORTED` until P5-C freezes its
  concrete representation.

The detailed field/dtype/shape/safety contract is maintained in
`REMOTE_IQA_V2_SPEC.md` and must stay synchronized with implementation/tests.

## Numerical hierarchy

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

Default absolute Dataset Overview remains pooled weighted mean.

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

Exact array names, dtypes, shapes, invalid projection encoding, path rules, and safety
ceilings are normative in `REMOTE_IQA_V2_SPEC.md`.

## Review findings being addressed

PR #40 first independent/orchestrator review accepted the architecture and requested
Stage-2 completion work. The implementation response is:

- **source reuse:** global source uniqueness removed; cross-Scene reuse with immutable
  metadata equality is supported; same-Scene duplicate binding remains explicitly
  invalid;
- **quality direction:** centralized Qt-free raw/quality conversion added for both
  power modes and reference reversal;
- **operator naming:** v2 switched from inherited A/B strings to target/reference
  strings while v1 names remain historical compatibility;
- **summary-first SMB boundary:** per-Scene filesystem stat/resolve removed from normal
  open; actual deferred artifact validation occurs on demand;
- **geometry:** exact equality is deliberately frozen and documented;
- **detail artifacts:** declared opaque/deferred rather than a permanent bare-path
  decode contract;
- **tests:** repository-native `tests/unit/test_remote_iqa_v2.py` added with hand-
  calculated numerical constants, source/context/cardinality/geometry/path/NPZ safety,
  PARTIAL/future-version, and real v1-dispatch coverage;
- **docs:** executable field placement/dtype/shape/safety/context rules are being
  reconciled in durable documentation.

## Repository-native Stage-2 validation gates

Before PR #40 leaves Draft, observe and record the focused suite first:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\unit\test_remote_iqa_v2.py `
    tests\unit\test_remote_iqa_v1.py
```

Then run the applicable repository checks because this PR changes `src/`, `tests/`,
scripts, and docs:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_docs_contract.py
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Only commands actually observed may be recorded as PASS. The earlier reconstructed
reduced-harness `32 passed, 1 deselected` result remains implementation evidence only;
it is not repository merge evidence.

## Later gates intentionally not solved here

P5-C owns:

- detailed PARTIAL/failure/cancel taxonomy and manifest shape;
- logical shared-storage-root client configuration;
- exact source-inspection/open authority;
- initial two-variant submission workflow and terminal API behavior.

P5-D owns typed spatial/detail consumption. It must define a versioned typed detail
sub-schema before interpreting optional detail data.

P5-F owns measured result-size, SMB latency, cache/preload budgets, and wall-clock
performance policy.

## Required sequence

```text
P5-A / schema v1 merged (#37)
        ↓
P5-A2 Stage 1 durable v2 contract merged (#39)
        ↓
P5-A2 Stage 2 executable v2 migration (#40, current)
        ↓
independent review + owner validation
        ↓
merge #40 to main
        ↓
rebase P5-B / #38 onto executable v2 main
        ↓
revise P5-B semantics and re-review
```

PR #38 remains untouched while #40 is active. Stage 2 must not merge until the durable
schema, repository-native tests, and observed validation agree.