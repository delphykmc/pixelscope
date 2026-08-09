# Execution plan: P3 — Image Semantics & RAW Processing

Status: Active
Owner: repository owner + P3 orchestration agents
Last updated: 2026-08-09
P3 program base: P2-F / PR #20 merge commit
`9c66629f6392971b8c52ac9dff27b16166cf9829`

## Goal

Stabilize image-comparison semantics across grayscale and mixed bit depths first,
then expand RAW processing and profile workflows on top of the completed P2
runtime foundation.

P3 deliberately precedes Workflow & Session Productivity. Session persistence and
workflow features should capture stable image-analysis semantics rather than
encode compatibility rules that are about to change.

## Program sequence

`P3-0 → P3-A → P3-B → P3-C → P3-D → P3-E`

| Order | Slice | Purpose | Merge prerequisite |
|---|---|---|---|
| 0 | P3-0 roadmap transition | Close/archive P2 and establish P3 | P2-F merged |
| 1 | P3-A Difference domain extension | Gray + mixed-bit Difference semantics | P3-0 merged |
| 2 | P3-B RAW processing semantics | Black/white-level and native/processed domain boundary | P3-A merged |
| 3 | P3-C Demosaic integration | Demosaic viewing/analysis without losing native-source authority | P3-B merged |
| 4 | P3-D RAW profile management | Reusable profiles and profile suggestion workflow | P3-C merged |
| 5 | P3-E integration hardening | Cross-analysis regressions, docs, Windows characterization | P3-D merged |

Each implementation slice starts from the latest merged prerequisite on `main`.
The exact branch/PR breakdown may be refined by the P3 orchestra, but the semantic
ordering above is authoritative unless a new owner decision changes it.

## Why P3 and P4 are reordered

The previous roadmap placed Workflow & Session Productivity before RAW work. The
order is changed because the next known product limitation is a core image-
semantics issue, not a workflow feature:

- Difference currently rejects GRAY in the standard compatibility path.
- Different bit depths cannot be compared through the intended normalized domain.
- RAW processing will introduce explicit black/white-level and demosaic semantics
  that must remain distinct from Difference full-scale normalization.
- Persistent sessions and saved analysis state should be built after these
  semantics are stable.

Therefore:

- **P3 becomes Image Semantics & RAW Processing.**
- **P4 becomes Workflow & Session Productivity.**
- P5–P7 retain their previous order.

## P3-0 — Program transition

Status: Active in the roadmap-transition documentation PR.

- Record P2-F / PR #20 as merged.
- Archive the completed P2 execution plan.
- Replace the active execution plan with this P3 program.
- Reorder P3/P4 in the durable roadmap.
- Record the current Difference limitation and the planned P3-A compatibility
  policy without changing runtime code.

This slice is documentation only.

## P3-A — Difference Gray / Mixed Bit-Depth Support

### Objective

Correct and extend the existing Difference capability without introducing a new
comparison mode or implicit color conversion.

### Compatibility policy

Supported families:

- `GRAY ↔ GRAY`;
- `RGB/RGBA ↔ RGB/RGBA`;
- Bayer ↔ Bayer only when the CFA pattern matches.

Rejected combinations:

- Gray ↔ RGB/RGBA;
- Gray ↔ Bayer;
- RGB/RGBA ↔ Bayer;
- different image dimensions;
- different Bayer CFA patterns.

No implicit RGB→Gray/luma conversion is introduced.

### Difference domains

**Same effective bit depth**

Preserve the existing native code-domain path and its compact integer Difference
cache.

Example UI semantics:

```text
Scope      Full image · Gray
Domain     Native · 10-bit
Threshold  10 code
```

**Different effective bit depths**

Normalize each source independently by its own full-scale code value to `[0, 1]`
and calculate Difference in that normalized domain.

Example UI semantics:

```text
Scope      Full image · Gray
Domain     Normalized [0–1]
Threshold  1.00 %FS
```

Do not convert one image into the other image's bit depth. Do not use RAW
black/white levels, display transforms, preview values, or demosaic output for
this normalization. This separation is intentional so P3-B RAW processing cannot
silently redefine P3-A Difference semantics.

### Runtime / cache target

- Preserve the existing same-bit native Difference fast path.
- Add GRAY explicitly to Difference family/channel selection; Gray exposes only
  the `Gray` channel.
- Use a normalized float32 Difference representation for mixed-bit comparisons.
- Avoid full-size float64 temporaries; use bounded/chunked computation for
  normalization and metrics where large images would otherwise multiply memory.
- Keep normalized metrics bounded-memory.
- Store explicit Difference-domain metadata (`native` / `normalized`) with cached
  results so threshold, metrics, restored views, and reversed-pair reuse cannot
  confuse domains.
- Prefer a structured compatibility result carrying family/domain/reason instead
  of propagating long free-form validation strings through the UI.

### UI target

Replace long sentence-style status text with compact structured fields such as:

```text
Scope    Full image · RGB combined
Domain   Native · 10-bit
```

or:

```text
Scope    Full image · Gray
Domain   Normalized [0–1]
```

Keep one Threshold control and change its semantics by domain:

- native: `code`;
- normalized: `%FS`.

Visible validation text should remain compact (`Layout mismatch`, `Size mismatch`,
`CFA mismatch`, etc.) with the detailed reason available through tooltip/help
text rather than a clipped status label.

### P3-A merge gates

Deterministic coverage should include:

- Gray Difference, mask, metrics, and channel selection;
- Gray invalid cross-family combinations;
- mixed-bit normalized equivalence against known full-scale values;
- same-bit native-path regression and cache representation;
- normalized threshold `%FS` semantics;
- cache identity and reversed-pair behavior across domains;
- large-image bounded-memory behavior without full-size float64 allocation;
- size/CFA/layout validation;
- compact status text plus detailed tooltip behavior;
- USER_GUIDE, architecture, decisions, quality, and current-state updates.

P3-A explicitly excludes RGB→Gray conversion, a new Difference mode selector,
RAW black/white-level normalization, demosaic, and unrelated workflow changes.

## P3-B — RAW Processing Semantics

Define the RAW processing boundary before adding richer display/analysis output.

Target areas:

- explicit black-level subtraction and white-level/full-scale handling;
- clipping/normalization semantics with overflow-safe arithmetic;
- clear ownership of **native decoded source** versus **processed RAW data**;
- cache/generation invalidation rules for processed representations;
- Settings/profile ownership only where a persistent user choice is justified;
- deterministic RAW10/12/14 and unpacked uint8/uint16 coverage.

P3-B must not retroactively redefine P3-A mixed-bit Difference normalization:
P3-A remains source full-scale based unless a future explicit Difference feature
is separately designed.

## P3-C — Demosaic Integration

Add demosaic as an explicit RAW processing/viewing boundary while preserving
native Bayer authority for workflows that require mosaic data.

Target areas:

- deterministic demosaic algorithm/interface boundary;
- native Bayer versus demosaiced RGB analysis semantics;
- preview/display integration without silently replacing native source data;
- cache/generation and worker ownership;
- Statistics/Histogram/Line Profile/Difference interaction made explicit rather
  than inferred from display pixels.

Avoid broad UI redesign or multiple experimental demosaic modes unless separately
approved.

## P3-D — RAW Profile Management

Build the reusable profile workflow after RAW processing semantics are stable.

Target areas:

- reusable profile storage/selection;
- clear profile identity/versioning;
- safe edit/duplicate/delete behavior if introduced;
- profile suggestion based on deterministic metadata/size evidence;
- no silent profile application when evidence is ambiguous;
- compatibility with existing JSON profile migration and exact-size policy.

## P3-E — Integration & Hardening

Close P3 over the completed Difference/RAW semantics.

- Cross-check native/normalized Difference and RAW processing ownership.
- Characterize representative Gray/RGB/Bayer/RAW and bit-depth combinations.
- Preserve P2 residency/preload/diagnostics contracts.
- Verify Statistics/Histogram/Line Profile/Difference/Split Channels regressions.
- Complete Windows characterization and durable P3 documentation.
- Do not add unrelated workflow/session features as part of phase closure.

## Cross-phase invariants

P3 builds on, and must preserve unless explicitly redesigned:

- P2 settings schema v5 migration/future-schema safety;
- exact native decoded-source residency accounting and protected soft-budget LRU;
- independent Difference Map Cache budget ownership;
- `+1`, one-position, max-one preload with foreground priority;
- exact RUNNING preload promotion without duplicate decode;
- advisory cancellation plus token/generation/request stale-result authority;
- observation-only sanitized **Help > Copy Diagnostics**;
- idempotent identical Statistics/Histogram numerical requests;
- expensive I/O/numerics off the UI thread;
- source dtype/channel meaning explicit and overflow-safe arithmetic.

A P3 slice may extend Difference cache metadata or RAW-derived representations,
but it must not collapse source residency, Difference cache, previews, or processed
RAW data into one ambiguous memory owner.

## Explicit P3 exclusions

Unless independently approved, P3 does not include:

- persistent comparison sessions;
- Recent Files/Folders;
- saved ROI management;
- arbitrary-angle line sampling;
- alpha overlay;
- remote IQA submission/service work;
- login/SSO/credential lifecycle;
- installer/signing/updater work;
- broad shortcut or MainWindow rewrite;
- speculative preload concurrency/resource-policy expansion;
- native C/C++ optimization without profiling evidence.

These remain later roadmap work.

## Validation policy

For runtime slices, use focused tests during development and the full repository
contract before completion:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

For this P3-0 documentation-only transition, the applicable checks are:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_docs_contract.py
git diff --check
```

Do not claim validation passed unless its output was actually observed.

## P3 exit criteria

P3 is complete when:

- Gray Difference works within explicit family compatibility rules;
- mixed-bit Difference has a deterministic normalized `[0,1]` domain with `%FS`
  threshold semantics and bounded-memory implementation;
- same-bit native Difference behavior/performance remains intact;
- RAW black/white-level and native/processed ownership are explicit;
- demosaic integration does not erase native Bayer authority;
- reusable profile management/suggestion is deterministic and safe;
- existing P2 runtime/resource/diagnostic contracts remain stable;
- full automated and agreed Windows validation pass;
- durable docs describe the final Difference and RAW domains without ambiguity.

## Later roadmap after P3

- **P4 — Workflow & Session Productivity:** persistent comparison sessions,
  Recent Files/Folders, saved ROI manager, arbitrary-angle line sampling, alpha
  overlay, and broader productivity/export workflows.
- **P5 — Remote IQA Platform:** remote submission/results, server/job API, GPU
  worker, artifact/heatmap/result comparison.
- **P6 — Identity, Access & Remote Operations:** login/SSO, token lifecycle,
  permissions, and operational administration.
- **P7 — Release Engineering & Distribution:** PyInstaller 5.7 `onedir`, portable
  ZIP, Inno Setup, clean-PC smoke, signing, updater/release process.
