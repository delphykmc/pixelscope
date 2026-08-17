# Execution plan: P5 — Remote IQA Platform

Status: Active — P5-0 program setup / contract hardening
Owner: repository owner + P5 orchestrator + slice implementation/review agents
Last updated: 2026-08-17
Inherited merged baseline: PR #35 / main
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`

Authoritative P5 documents:

- product/architecture contract:
  [`docs/REMOTE_IQA_CONTRACT.md`](../../REMOTE_IQA_CONTRACT.md)
- normative P5-v1 math/identity/geometry/artifact specification:
  [`docs/REMOTE_IQA_V1_SPEC.md`](../../REMOTE_IQA_V1_SPEC.md)
- completed P4 plan:
  [`docs/exec-plans/completed/p4-workflow-session-productivity.md`](../completed/p4-workflow-session-productivity.md)

## Program-governance model

P5 is run as an orchestrated multi-PR program.

- **P5 orchestrator** owns this execution plan, durable cross-slice contracts, scope
  boundaries, owner-decision tracking, and evaluation of implementation/review
  evidence. The orchestrator discusses unresolved product/algorithm policy with the
  repository owner and updates the plan before delegating affected implementation.
- **Slice implementation agents** implement only their named P5 slice against latest
  `main` plus the durable P5 documents. They do not redefine cross-phase contracts
  implicitly in code.
- **Independent review agents** review the latest PR head as a whole against ROADMAP,
  the P5 contracts, inherited P2/P3/P4 authorities, tests, resource/lifetime behavior,
  and durable docs. They do not directly modify code/docs.
- **Repository owner** supplies unresolved product/server-policy decisions and runs
  the requested local Windows validation for runtime/UI slices.

When an implementation exposes a missing cross-slice decision, implementation should
stop at the existing contract boundary; the orchestrator/owner resolves the policy
and updates durable docs before implementation continues.

## Goal

P5 connects PixelScope to an external GPU Image Quality Assessment service while
preserving PixelScope as a fast local image-comparison tool.

The intended user flow is:

1. inspect images rapidly with existing PixelScope tools;
2. submit a deterministic current pair or large folder-pair evaluation when remote
   IQA is useful;
3. continue ordinary local work while a remote job runs;
4. reopen immutable historical IQA results without rerunning the GPU job;
5. drill down `dataset → attribute → scene → spatial block`;
6. explicitly connect an interesting Scene back to the existing PixelScope viewer.

GPU model/server implementation remains in its external repository. PixelScope owns
client-side preparation, stable result parsing, local derived exploration, result
history, and viewer integration.

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

P5 must not accidentally create another authority for source identity, Files,
Selected, Current Comparison Page, residency/protection, preload, source generation,
Difference/cache, Display Gain, or Session v1.

Remote batch membership/result browsing is feature-local. Passive IQA work does not
register/decode/protect all batch sources or change current local analysis state.

## Frozen P5-v1 contract highlights

The detailed normative rules live in `REMOTE_IQA_V1_SPEC.md`; implementation agents
must not replace them with inferred alternatives.

### Remote model

```text
IQA Job
    ↓
Scene
    ├─ ordered sources[] with stable source_id
    ├─ representative image
    ├─ common PiDiNet Edge Map
    ├─ common Texture Gate
    └─ per-source attribute data
          ↓
     comparisons by stable operand IDs
```

P5 v1 UI is two-source; durable schema includes a 3-source structural test.

### Numerical orientation

- power raw comparison: A/B in dB;
- signed bias: A-B;
- higher-is-better quality sign = raw sign;
- lower-is-better quality sign = inverted raw sign;
- per-power-attribute epsilon is mandatory versioned result metadata;
- Tier-2 compact data requires W/S1/S2/count/valid fields;
- pairwise valid blocks use A-valid ∩ B-valid;
- official comparison modes are ratio-of-weighted-means and arithmetic mean of
  valid per-grid dB values;
- invalid statistics are explicit null+reason, never JSON NaN/Infinity.

### Coordinate convention

- continuous pixel-edge coordinates;
- half-open pixels/cells/valid rectangles;
- row-major source→analysis 3×3 affine;
- grid origin is a pixel edge;
- only full contained blocks are serialized;
- inverse mapping remains continuous until viewer/raster boundary;
- P5-A must include non-integer scale + non-zero crop/origin geometry.

### Remote input/pairing

- v1 remote file families: PNG/JPG/JPEG/BMP only; RAW has no implicit conversion;
- Current Pair requires exactly two eligible native Current Comparison Page sources;
- A/B follows underlying page/Selected source order, not Primary/Active/view reorder;
- Folder Pair is immediate-directory, non-symlink, case-insensitive extension filter,
  Unicode-NFC lexical ordering by `(casefold(name), name)`;
- counts must match and the complete Pair Preview is shown;
- explicit Scene manifest is authoritative; server does not re-sort it.

### Result safety/publication

- top-level `kind = pixelscope-iqa-result`, `schema_version = 1`;
- unsupported newer schema fails without mutation;
- all artifact references remain beneath result root;
- NumPy is `allow_pickle=False`, dtype/rank/shape/size validated;
- compact artifact safety caps are specified in the v1 spec;
- final complete manifest is the publication commit marker;
- no result-bearing terminal state, including the owner-approved PARTIAL direction,
  may be reported/openable before required Tier-1/2 publication.

## UX direction

P5 adds one non-modal IQA workspace/dock:

```text
IQA
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
└─ Results
```

Native OS file/folder pickers may remain modal. Pair preparation, job progress, and
result exploration remain non-modal.

Result browsing follows:

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

Passive browsing never mutates Selected. Explicit Inspect Pair uses the canonical
local registration/selection path for only the chosen Scene pair. IQA Reference is
separate from Primary. P5 v1 blocks Inspect while temporary P4-A Picks are active.
Return-to-previous-workspace is transient and is invalidated rather than applied over
newer non-IQA Selected/workspace intent.

## Program sequence

`P5-0 → P5-A → P5-B → P5-C → P5-D → P5-E → P5-F → P5 Complete`

| Order | Slice | Status |
|---|---|---|
| 0 | P5-0 P4 Closure & P5 Program Setup | Active — review follow-up |
| 1 | P5-A Contract Fixtures & IQA Domain | Planned |
| 2 | P5-B IQA Workspace & Local Result Exploration | Planned |
| 3 | P5-C Submission & Shared Storage | Planned — C1 + detailed terminal gates pending; PARTIAL allowed |
| 4 | P5-D Viewer-linked Scene Inspection | Planned |
| 5 | P5-E Historical Result Workflow | Planned |
| 6 | P5-F Integration & Performance Hardening | Planned |

## P5-0 — P4 Closure & P5 Program Setup

### Goal

Freeze a sufficiently deterministic contract that two independent P5-A agents cannot
produce incompatible implementations while both claiming compliance.

### Deliverables

- P4 archive and PR #35 closure baseline;
- ROADMAP/CURRENT_STATE/UI-status transition to P5;
- active P5 orchestration plan;
- broad Remote IQA product contract;
- normative P5-v1 specification for numerical orientation, compact sufficient
  statistics, validity, coordinates, pair/source identity, safe artifacts, and
  immutable publication;
- explicit owner-decision gates for policies that legitimately belong to P5-C;
- no runtime/UI code or Settings/Session schema change in P5-0 itself.

### Merge gates

- independent review of latest head finds no unresolved P5-A contract blocker;
- docs-only owner validation:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_docs_contract.py
git diff --check
```

Full runtime pytest/Ruff/mypy is not required solely because P5-0 changes Markdown.

## P5-A — Contract Fixtures & IQA Domain

### Goal

Make the intended GPU/result contract executable and reviewable without a live server.

### Required implementation

- Qt-free versioned domain models for Result/Scene/Source/Attribute/comparison;
- exact `pixelscope-iqa-result` schema-v1 manifest parser;
- Tier-1 summary and Tier-2 compact scene parser with all v1 safety rules;
- deterministic production-shaped fixture/result generator;
- local mean/std/raw/quality/aggregation recomposition matching authoritative golden
  fixture values;
- source→analysis geometry/inverse-mapping utilities;
- explicit invalid/corrupt/unsupported result models without UI dependency;
- current remote skeleton may be adapted, but P5-A does not require live HTTP.

### Required fixtures/tests

Primary fixture: roughly 10–12 Scenes × 2 sources × all ten attributes, deliberately
structured for trends/outliers rather than random-only data.

It must prove:

- dynamic server-driven block sizes including a non-default variant;
- epsilon-controlled near-zero power golden result;
- power A/B orientation and quality-sign inversion for noise;
- signed bias A-B across negative/zero/positive;
- W/S1/S2/count/valid weighted mean/std recomposition;
- valid-grid intersection;
- both official aggregation modes with a case where they differ;
- zero-weight/no-valid explicit invalid result;
- non-integer affine scale + non-zero valid/grid origin + discarded border;
- identical-source case;
- path traversal / unsafe object array / malformed shape / oversized artifact failure;
- missing/corrupt compact artifact;
- incomplete publication rejection;
- optional detail absent/present;
- dimension mismatch model;
- at least one 3-source structural Scene proving N-source schema identity.

Large real 2K maps are not committed.

### Acceptance

With no network/GPU service, P5-A tests can independently reproduce fixture-authority
math and geometry from the versioned artifact and reject incompatible/unsafe data.
No UI implementation is required.

## P5-B — IQA Workspace & Local Result Exploration

### Goal

Prove the user-facing result hierarchy entirely against P5-A artifacts before live
submission/storage integration.

### Scope

- non-modal IQA workspace/dock shell;
- the **canonical** `Open IQA Result...` controller/parser path;
- Job/dataset overview;
- Attribute × Scene overview plus selected-attribute trend/outliers;
- explicit selection of the two official aggregation modes;
- result-only local/fixture exploration;
- no passive Files/Selected/native-analysis mutation;
- close/recreate and stale callback safety.

P5-B does not create a second source authority and does not require live HTTP.

## P5-C — Submission & Shared Storage

### Goal

Connect the proven P5-A/P5-B artifact/UX path to the external GPU service.

### Owner-decision gates — must be closed before implementation starts

#### Gate C1 — logical storage-root configuration ownership

C1 remains intentionally deferred. Before P5-C starts, choose and document one
machine-local authority for:

```text
storage_root_id → client path / UNC path
```

Preferred candidate is typed `ApplicationSettings` with an explicit Settings schema
migration if the model fits. A feature-local repository is acceptable only if it does
not create a competing settings authority and is durably justified. Result artifacts
and Session are prohibited from becoming machine-local mapping authority.

#### Gate C2 — PARTIAL allowed; detailed terminal contract pending

The owner has fixed the central policy: **durable PARTIAL results are allowed**.
A Scene-level failure must not automatically discard otherwise valid successful Scene
results. P5-C must preserve successful Scene outputs whenever the final terminal/
publication policy classifies them as a publishable partial result.

Before P5-C starts, freeze the remaining details:

- request-level validation/rejection behavior;
- per-Scene failure record schema and reason taxonomy;
- exact PARTIAL terminal-state identity and API representation;
- required Tier-1/Tier-2 artifacts for successful versus failed Scenes;
- behavior when no Scene succeeds;
- cancel versus completion/publication race semantics.

The implementation agent must not re-decide whether PARTIAL is allowed and must not
invent the remaining details.

### Scope after gates close

- logical storage-root mapping and safe shared staging;
- deterministic Current Pair submission;
- deterministic two-folder Pair Preview/count blocking;
- explicit Scene manifest request;
- HTTP submit/status/result/cancel adapter, polling first;
- non-modal Jobs progress;
- result handoff into the exact P5-B canonical Open Result/repository path;
- retry/failure/cancel behavior under the finalized C2 terminal contract;
- no local batch Files/Selected/residency authority.

Server implementation remains outside this repository.

## P5-D — Viewer-linked Scene Inspection

### Goal

Connect result anomalies to existing source-image viewing without a new image-source
or local-analysis authority.

### Scope

- explicit Inspect Pair;
- canonical registration/selection of only the inspected two-source Scene;
- P4-A active Pick guard;
- transient return snapshot and v1 invalidation policy;
- IQA Reference separate from Primary;
- Scene navigation linked to existing viewer after Inspect starts;
- exact v1 grid→analysis→source→viewer mapping;
- vector/grid overlay using compact Tier-2 data;
- block inspector with source means/raw comparison/quality direction/geometry;
- missing/hash-mismatch source degradation;
- no Difference/ROI/Line/Display-Gain semantic changes.

## P5-E — Historical Result Workflow

### Goal

Make completed remote results durable reusable engineering records.

### Scope

- **extend the P5-B canonical Open Result path; do not introduce another one**;
- bounded Recent IQA Results;
- production logical-root reopen;
- immutable job/result identity and source hashes;
- result-only mode when sources are unavailable;
- source/hash mismatch diagnostics;
- user/purpose/project provenance presentation where available;
- history references result identity/path, not copied arrays in Session.

P5 does not modify Session v1. A future result-reference-in-Session feature requires a
new explicit Session schema/version decision outside this implicit scope.
Authentication/SSO/token/permission/admin operations remain P6.

## P5-F — Integration & Performance Hardening

### Goal

Validate real-server and large-dataset composition while preserving every inherited
local authority/lifecycle contract.

### Scope

- real server compatibility against versioned v1 contract;
- large-result lazy loading and bounded cache characterization;
- SMB/network bandwidth behavior;
- current-pair and large-folder stress;
- cancellation/failure/missing-artifact/application close/recreate;
- no eager all-Scene/all-source loading;
- no batch-driven Files/Selected/residency/preload authority;
- polling/task teardown and stale-result rejection;
- optional Tier-3 detail characterization without making it normal-path mandatory;
- durable P5 closure docs.

No wall-clock threshold is a correctness merge gate. Deterministic gates are correct
identity/math/geometry, bounded ownership/loading, no duplicate remote work, stale
callback rejection, and teardown safety.

## Review workflow for every runtime slice

1. orchestrator confirms latest `main`, previous P5 merges, and unresolved owner gates;
2. implementation agent receives a slice-specific prompt derived from this plan;
3. implementation stays within that slice and commits intentional subunits;
4. owner runs requested focused Windows validation;
5. implementation agent opens the PR with goals, contract preservation, test evidence,
   exclusions, and `Co-authored-by: ChatGPT <noreply@openai.com>` where agent-generated;
6. independent reviewer checks latest full head against ROADMAP/P5 specs/inherited
   architecture, tests, resource/lifetime behavior, and docs;
7. orchestrator classifies findings as implementation defect, missing contract, or
   owner-decision request;
8. implementation agent fixes implementation defects; orchestrator/owner resolves
   contract decisions before code that depends on them continues;
9. latest head is re-reviewed when blockers were found;
10. only then does the orchestrator recommend merge and prepare the next slice prompt.

## Validation policy

### Docs-only slices

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_docs_contract.py
git diff --check
```

### Runtime/UI slices

The repository owner uses the existing Windows `.venv`; implementation agents do not
spend work trying to bootstrap/search an unknown local environment.

Run focused tests first, then repository-standard checks before merge as appropriate:

```powershell
.\.venv\Scripts\python.exe -m pytest -q <focused tests>
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Only observed validation is recorded as PASS.