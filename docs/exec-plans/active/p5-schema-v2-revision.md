# Execution note: P5 IQA schema v2 source-measurement revision

Status: Active contract revision — PR #39 review updates
Owner: repository owner + P5 orchestrator
Base: `main@fceb16f6e43c48ec65fbf7ebbcc103b56716b686` (P5-A / PR #37 merged)
Schema target: [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)

## Why this interruption exists

P5-A/schema v1 successfully proved versioned result parsing, compact sufficient
statistics, geometry, safety, and fixture-first numerical validation. P5-B then exposed
a cross-slice ownership problem: a pairwise-centered stored result is workable for
A/B, but does not scale cleanly to A/B/C/D-style variants with a freely switchable IQA
Reference.

The P5 program therefore pauses schema-dependent P5-B work and resolves the numerical
contract on `main` first. The current P5-B branch/PR #38 is not the authority for this
revision and must not carry an implicit competing schema.

## Accepted architecture direction

The owner, P5 orchestrator, and independent schema review agree on the central model:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

The server owns:

- source decoding and analysis-domain preparation;
- IQA attribute signal extraction;
- Scene-context weighting/gating and valid-grid decisions;
- compatible grid geometry;
- W/S1/S2/count/valid sufficient statistics;
- canonical source-local summary statistics;
- measurement/model/preprocessing/weighting provenance.

PixelScope owns:

- `variant_id`-based IQA Reference selection;
- arbitrary local target/reference comparison;
- comparison-mode selection;
- Dataset Overview and Scene Trend presentation;
- local derived statistics;
- grid-relative values and spatial colormap/overlay presentation;
- bounded asynchronous loading/cache policy for compact analytical artifacts.

## Scene-context boundary

"Absolute" means reference-independent inside one published Scene evaluation context;
it does not mean globally context-free.

Because representative-image structural context, Edge Map, Texture Gate, and effective
weights can depend on the Scene cohort, a weighted source measurement cannot be reused
across another incompatible Scene/job/cohort merely because the same source hash is
present. Schema v2 therefore requires a stable `measurement_context_id` or equivalent
fingerprint tied to cohort/source, preprocessing/model, geometry, and weighting
provenance.

Server implementations may reuse lower-level cached features where mathematically
valid, but the published weighted measurement remains scoped to its Scene evaluation
context.

## Identity and complete-result invariants

Schema v2 adds dataset-level `variant_id` separately from concrete `source_id`.

```text
variant A: source A-0001, A-0002, A-0003 ...
variant B: source B-0001, B-0002, B-0003 ...
variant C: source C-0001, C-0002, C-0003 ...
```

For a normal non-PARTIAL complete result:

- top-level variants are unique and stable;
- one Scene contains exactly one source per declared `variant_id`;
- source IDs remain unique concrete-image identities;
- one Scene cannot bind two sources to one variant;
- all participating variants in one Scene/attribute share compatible/equivalent grid
  topology and physical cell correspondence;
- original dimensions match; PixelScope never aligns or resizes an incompatible
  cohort to manufacture comparison data.

The detailed missing-variant rules for PARTIAL output remain a P5-C terminal/failure
contract concern.

## Numerical reduction hierarchy frozen by owner decision

### Scene absolute value

The canonical `Scene × source × attribute` absolute mean is the weighted sufficient-
statistic reduction:

```text
scene_mean = Σ S1[g] / Σ W[g]
```

The matching weighted population std is recomposed from ΣW/ΣS1/ΣS2. An arithmetic
mean of grid means is not another unnamed `mean`; any future equal-grid statistic must
have a distinct name.

### Dataset absolute values

Schema v2 publishes both:

1. `pooled_weighted_mean` / pooled weighted std from W/S1/S2 accumulated across valid
   Scenes;
2. `scene_mean` / `scene_std` across valid canonical Scene means with equal Scene
   contribution.

**Owner-selected default absolute Dataset Overview: `pooled_weighted_mean`.**

The equal-Scene statistics remain available as secondary engineering information.

### Fast summary authority rule

W/S1/S2/count/valid + the normative formulas are the numerical authority. Serialized
Scene/dataset mean/std values are server-authored fast projections and must agree with
deterministic recomposition within the schema-v2 tolerance. A mismatch is invalid/
corrupt; the client does not choose between competing values.

### Scene relative comparison

Reference-dependent comparison uses the pair-valid grid intersection for one
Scene/attribute.

- power ratio mode: ratio of pair-valid aggregate weighted means;
- grid-log-ratio mode: arithmetic mean of finite pair-valid grid dB values;
- signed mode: pair-valid weighted target mean minus pair-valid weighted reference
  mean.

### Dataset relative Overview

**Owner-selected default relative Dataset Overview:**

```text
1. compute the selected target/reference comparison independently per valid Scene;
2. arithmetic-mean those valid Scene comparison values.
```

The rule applies consistently to both power modes and signed deltas. This makes the
relative Overview the equal-Scene reduction of Scene Trend. A pooled-across-Scenes
relative mode may be added later only as a separately named mode.

## Result data categories

The old numerical statement `Tier 1 summary / Tier 2 inspected-Scene compact / Tier 3
detail` is replaced by purpose-based artifact categories:

1. **Summary metadata** — small open-time absolute Dataset + Scene summaries.
2. **Grid measurement artifacts** — primary analytical source for exact local
   target/reference calculations and spatial views.
3. **Optional detail artifacts** — larger per-pixel/2K/debug material.

Schema semantics do not choose always-eager versus inspected-Scene-only loading.
PixelScope may read grids by Scene, bounded batch, background work, or bounded cache.
The runtime policy must remain non-blocking, bounded, and stale-safe, especially on
SMB/network storage.

## PARTIAL direction carried forward

The existing owner decision remains active:

> **Durable PARTIAL results are allowed and successful Scene work must be
> preservable when another Scene fails.**

This schema revision does not reopen that policy. P5-C still must freeze the detailed
request rejection, missing-variant/per-Scene failure record, exact PARTIAL terminal
identity, no-success behavior, required publication artifacts, and cancel/publication
race rules.

## v1 compatibility policy frozen

- v2 becomes current/default after the executable migration lands;
- v1 remains explicit read-only compatibility for historical two-source results and
  fixtures;
- no silent upgrade invents v2 absolute measurements from v1 pairwise summaries;
- v1 UX may be limited to fields actually present in v1;
- new writers/fixtures target v2 after migration.

`REMOTE_IQA_V1_SPEC.md` remains historical and is not rewritten.

## P5-C submission cardinality owner decision

Schema-v2 result identity remains N-way-capable, but that capability does not force the
first submission UI to expose arbitrary N-way input.

The current owner decision is:

- P5-C request/result identity remains N-way-capable through explicit ordered Scene
  manifests;
- the **initial P5-C submission UI remains two-variant only**;
- Current Pair submits exactly two variants;
- batch submission remains the deterministic two-folder Pair workflow;
- arbitrary three-or-more-variant submission UI is deferred and requires a later
  explicit owner decision;
- P5-B still supports N-way v2 result exploration and Reference switching regardless
  of how the initial submission UI is scoped.

This keeps schema capability separate from product/UI scope and prevents P5-C from
silently expanding merely because schema v2 can represent more variants.

## Implementation-blocking versus later gates

### Must be frozen/implemented in the focused executable-v2 migration

Before P5-B resumes, the v2 domain/fixture/parser migration must define and test:

- concrete schema-v2 manifest/summary/grid field names and dtype/shape rules;
- JSON-versus-NPZ placement;
- justified schema-v2 safety ceilings;
- `measurement_context_id` encoding/fingerprint construction;
- complete-result variant/cardinality and grid-correspondence validation;
- summary-projection consistency validation;
- v1 read-only compatibility dispatch;
- deterministic v2 fixtures/goldens for N-way identity and every reduction mode.

These are not choices that the rebased P5-B agent may invent.

### May remain for later P5 slices

- detailed PARTIAL/failure/cancel taxonomy: P5-C;
- machine-local logical-root configuration ownership: P5-C;
- arbitrary N-way submission UI: later owner-approved follow-up;
- final cache/preload budget and wall-clock targets: P5-F.

## Required program sequence

```text
P5-A / schema v1 merged (#37)
        ↓
PR #39 schema-v2 durable contract review
        ↓
merge accepted docs/schema contract to main
        ↓
focused executable-v2 domain/fixture/parser migration
        ↓
merge executable-v2 baseline to main
        ↓
rebase P5-B / PR #38 onto that main
        ↓
revise P5-B for v2 semantics
        ↓
independent P5-B re-review
```

P5-B must not resume schema-dependent behavior immediately after the docs-only PR #39
merge; it resumes only after the executable-v2 migration is merged.

## P5-B rebase requirements

The rebased P5-B must:

- support N-way `variant_id` Reference selection;
- show initial absolute Dataset/Scene views from small server summary metadata;
- default absolute Dataset Overview to `pooled_weighted_mean`;
- derive arbitrary target/reference values locally from accepted source measurements;
- default relative Dataset Overview to arithmetic mean of valid Scene comparisons;
- preserve the selected power comparison mode and signed-delta semantics;
- run required grid I/O/calculation outside the Qt UI thread;
- expose compact Loading/Calculating state when appropriate;
- reject stale asynchronous results;
- preserve Files/Selected/Primary/residency/native Statistics/Difference during
  passive result browsing;
- leave actual historical source opening to logical-root/hash/canonical Inspect
  authority.

## Validation for this docs-only revision

This branch changes documentation/schema contracts only. Required owner/local
validation before merge is:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_docs_contract.py
git diff --check
```

Full runtime pytest/Ruff/mypy is not required solely for this Markdown contract
revision unless another changed dependency makes it necessary.

## Explicit non-goals

PR #39 does not:

- modify P5-B runtime/UI code or branch history;
- implement schema-v2 Python models/readers;
- modify the external GPU server repository;
- freeze the complete PARTIAL/failure transport taxonomy;
- implement logical storage-root mapping or source hash inspection;
- expose arbitrary N-way submission UI in the initial P5-C slice;
- choose final grid cache/preload budgets;
- merge/rebase P5-B.
