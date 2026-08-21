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
- `source_id` may recur across different Scenes **or multiple variant slots in the
  same Scene** when immutable source metadata is identical;
- each COMPLETE Scene still binds every declared `variant_id` exactly once in exact
  top-level variant order;
- a repeated `source_id` with different `relative_path`, SHA-256, width, or height is
  invalid anywhere in the result;
- weighted measurement identity remains Scene-context scoped by deterministic
  `measurement_context_id`;
- context format is `mc2:<sha256>` over canonical JSON with `float.hex()` geometry
  tokens and ordered `(variant_id, source_id, ...)` membership;
- original dimensions match across Scene variants;
- duplicated SceneGeometry and per-attribute GridGeometry are required to compare
  exactly equal across Scene variants;
- v2 operator names are reference-neutral:
  `power_ratio_target_over_reference_db` and `signed_target_minus_reference`;
- one Qt-free v2 comparison authority returns both raw engineering orientation and
  user-facing quality orientation;
- higher-is-better power uses `quality = raw`, lower-is-better uses `quality = -raw`
  for both power modes, and signed/neutral quality is N/A;
- power Mode 2 is v2-owned and averages only **finite** pair-valid per-grid dB ratios;
  undefined/non-finite cells such as epsilon-zero `0/0` are skipped if other finite
  cells remain, while no finite value yields an explicit invalid Mode-2 result;
- ordinary result open touches only `manifest.json` and `summary.npz`; deferred grid/
  detail references receive syntax-only path validation at open and filesystem access
  is deferred to the requested artifact;
- optional `detail_artifacts` are opaque bounded references in Stage 2, not a frozen
  P5-D decode schema;
- `publication_state=partial` is explicitly `UNSUPPORTED` until P5-C freezes its
  concrete representation;
- the aggregate 1024 Scene-source-binding ceiling is a deliberate parser acceptance
  envelope: Stage-1 planning assumed roughly 300 compared source images, so the cap
  gives >3x headroom and still permits all 512 Scenes for the initial two-variant
  workflow.

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
- power mode 2: unweighted arithmetic mean of **finite** pair-valid grid log-ratios;
- signed: pair-valid weighted target mean minus reference mean.

For mode 2, an undefined/non-finite individual grid ratio contributes no sample when
other finite ratios exist. If no finite grid ratio remains the Mode-2 result is
invalid. Negative power-domain values are invalid input rather than skippable data.

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

## Latest review findings addressed

The first independent/orchestrator pass accepted the architecture and requested
source-reuse, quality-direction, repository-test, summary-first and durable-doc
completion. Those findings were implemented. The next meticulous pass identified four
additional closure issues, now addressed in the branch:

1. **Mode-2 finite reduction:** v2 no longer inherits v1's fail-fast per-cell ratio
   behavior. Mixed undefined/finite pair-valid cells keep the finite samples, with
   dedicated review regression coverage.
2. **Same-Scene concrete-source reuse:** the hybrid uniqueness rule was removed.
   `variant_id` is the slot identity and the same concrete `source_id` may occupy
   multiple variant slots when immutable metadata is identical. An identical-source
   zero-delta sanity case is covered.
3. **Durable system-of-record drift:** `ARCHITECTURE.md`, `DECISIONS.md`, `QUALITY.md`,
   `next-phase.md`, this execution note, and the v2 spec now describe the executable
   v2 authority rather than leaving Stage-1/v1 wording as current state.
4. **1024 source-binding rationale:** the cap is explicitly documented as a deliberate
   result-acceptance envelope relative to the roughly 300-source Stage-1 production
   assumption, not as an unexplained cache or arbitrary product limit.

Repository-native Stage-2 tests are distributed across:

```text
tests/unit/test_remote_iqa_v2.py
tests/unit/test_remote_iqa_v2_limits.py
tests/unit/test_remote_iqa_v2_review_regressions.py
```

The real schema-v1 golden remains exercised through canonical dispatch rather than
being synthesized or rewritten.

## Repository-native Stage-2 validation gates

Before PR #40 leaves Draft, observe and record the focused suite first:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\unit\test_remote_iqa_v1.py `
    tests\unit\test_remote_iqa_v2.py `
    tests\unit\test_remote_iqa_v2_limits.py `
    tests\unit\test_remote_iqa_v2_review_regressions.py `
    tests\unit\test_remote.py
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
reduced-harness `32 passed, 1 deselected` result remains pre-review implementation
evidence only; it is not latest-head repository merge evidence.

## Later gates intentionally not solved here

P5-C owns:

- detailed PARTIAL/failure/cancel taxonomy and manifest shape;
- logical shared-storage-root client configuration;
- exact source-inspection/open authority;
- initial two-variant submission workflow and terminal API behavior.

P5-D owns typed spatial/detail consumption. It must define a versioned typed detail
sub-schema before interpreting optional detail data.

P5-F owns measured result-size, SMB latency, cache/preload budgets, and wall-clock
performance policy. If real production cardinality exceeds the Stage-2 1024-binding
acceptance envelope, P5-F evidence must feed a deliberate schema/safety revision rather
than bypassing the parser cap.

## Required sequence

```text
P5-A / schema v1 merged (#37)
        ↓
P5-A2 Stage 1 durable v2 contract merged (#39)
        ↓
P5-A2 Stage 2 executable v2 migration (#40, current)
        ↓
repository-pinned validation + independent latest-head review
        ↓
merge #40 to main
        ↓
rebase P5-B / #38 onto executable v2 main
        ↓
revise P5-B semantics and re-review
```

PR #38 remains untouched while #40 is active. Stage 2 must not merge until the durable
schema, repository-native tests, and observed validation agree.
