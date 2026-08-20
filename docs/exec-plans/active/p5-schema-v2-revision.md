# Execution note: P5 IQA schema v2 source-measurement revision

Status: Proposed — review/discussion PR before P5-B continuation
Owner: repository owner + P5 orchestrator
Base: `main@fceb16f6e43c48ec65fbf7ebbcc103b56716b686` (P5-A / PR #37 merged)
Schema proposal: [`docs/REMOTE_IQA_V2_SPEC.md`](../../REMOTE_IQA_V2_SPEC.md)

## Why this interruption exists

P5-A/schema v1 proved the result/domain mechanics, but P5-B UX work exposed a deeper
N-way ownership issue. A two-source A/B result can survive with server-authored
pairwise comparison records. A three/four-source result with a user-switchable
Reference should not require the server to serialize every pair and every comparison
mode.

The P5 program is therefore intentionally pausing schema-dependent P5-B semantics and
moving the cross-slice data-model decision back to `main` as a separate docs/schema
review PR.

The current P5-B branch is **not** the authority for this revision and must not be used
to smuggle schema changes into UI code.

## Owner direction captured by this proposal

- server-side IQA evaluation owns each image's attribute signal extraction;
- weighting/gating and valid-grid decisions are server authority;
- server publishes absolute per-source grid sufficient statistics;
- server also publishes small absolute dataset-level and Scene-level summaries for
  fast initial browsing;
- server does not need to publish every possible target/reference comparison;
- PixelScope chooses Reference locally and derives the requested relative comparison;
- PixelScope locally constructs Overview, Scene Trend, statistics, and spatial
  visualization from the server-authored measurement source;
- original source-size incompatibility and otherwise unevaluable pairs/cohorts are
  rejected/excluded by server evaluation rather than resized/aligned by PixelScope;
- the detailed exception/PARTIAL taxonomy is deferred to its dedicated failure
  contract and is not invented in this schema PR.

## Target architecture

```text
GPU server
    │
    ├─ manifest / identity / provenance
    │
    ├─ fast absolute summary
    │    ├─ dataset × variant × attribute
    │    └─ Scene × variant/source × attribute
    │
    └─ absolute grid measurement
         └─ Scene × variant/source × attribute × grid
              ├─ weight_sum
              ├─ weighted_sum
              ├─ weighted_square_sum
              ├─ valid_count
              └─ valid_mask

PixelScope
    │
    ├─ initial absolute Overview / Scene Trend from summary
    │
    ├─ Reference + comparison-mode selection
    │       ↓
    │   local derived target/reference values
    │
    ├─ Scene-retained result -> Scene Trend
    ├─ Scene-reduced result  -> Overview
    └─ grid-retained result  -> spatial visualization / P5-D
```

## Key schema change

Schema v2 introduces a dataset-level `variant_id` separate from per-image `source_id`.
This is necessary to identify the same comparison group/configuration across multiple
Scenes.

Example:

```text
variant A: source A-0001, A-0002, A-0003 ...
variant B: source B-0001, B-0002, B-0003 ...
variant C: source C-0001, C-0002, C-0003 ...
```

Reference selection targets a `variant_id`; Scene inspection still addresses concrete
`source_id` values.

## Result-level data categories

The old semantic statement `Tier 1 summary / Tier 2 inspected-Scene compact / Tier 3
detail` is intentionally revised.

Schema v2 should describe artifact purpose rather than hard-code one loading policy:

1. **Summary metadata** — small open-time absolute scalar/stat accumulator data.
2. **Grid measurement artifacts** — primary analytical data source for exact local
   relative calculations and spatial views.
3. **Optional detail artifacts** — larger per-pixel/debug data.

Whether grid artifacts are loaded per Scene, in bounded batches, in background, or
cached is a PixelScope performance decision. It is not numerical schema semantics.

## Expected workflow after this PR

1. Independent reviewer and P5 orchestrator review the schema proposal itself.
2. Owner resolves review questions/open numerical semantics in this PR.
3. Docs/schema PR merges to `main` only after the contract is accepted.
4. A focused schema-v2 implementation update makes domain/parser/fixture/golden tests
   executable against the accepted contract.
5. Current P5-B branch rebases onto the merged schema-v2 baseline.
6. P5-B is revised to consume fast absolute summaries first and compute arbitrary
   local reference comparisons from accepted measurement data.
7. P5-D uses the same absolute grid source for spatial relative visualization.

## P5-B rebase requirements

After this schema PR merges, P5-B must not merely resolve Git conflicts. Its behavioral
model must be reconciled:

- support `variant_id`-based N-way Reference selection;
- initial view may show absolute source/variant values from summary metadata;
- arbitrary relative values are local derived data, not server-authored official pair
  records;
- comparison calculation/loading must not block the Qt UI thread;
- calculation state can be visible while required measurement arrays are read;
- result browsing remains feature-local and cannot mutate Files/Selected/Primary,
  source residency, native Statistics, or Difference;
- direct opening of historical source pixels remains outside passive P5-B authority.

## Validation for this docs-only revision

Because this branch is intended to change documentation/schema contracts only, the
required local validation is the repository documentation contract and diff hygiene:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_docs_contract.py
git diff --check
```

Full runtime pytest/Ruff/mypy is not required solely for Markdown additions unless the
review process requests another repository policy check.

## Explicit non-goals

This PR does not:

- modify P5-B runtime/UI code;
- modify the current P5-B branch;
- implement schema-v2 parser/domain classes;
- change server code in the external repository;
- freeze the complete failure/PARTIAL taxonomy;
- implement logical storage-root configuration;
- implement source Inspect Pair/hash verification;
- choose final grid cache/preload budgets;
- merge or rebase P5-B.

Those occur only after this schema contract is reviewed and merged.
