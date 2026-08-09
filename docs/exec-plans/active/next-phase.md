# Execution plan: P3 — Image Semantics & RAW Processing

Status: Active
Owner: repository owner + P3 orchestration agents
Last updated: 2026-08-09
Current merged P3 baseline: roadmap replanning / PR #23 merge commit
`4c7d1bbbb4476134f76a204578098d35a03feca2`

## Goal

Stabilize image-comparison and RAW-viewing semantics while keeping PixelScope an
engineering inspection tool. Native decoded samples remain authoritative; viewer
presentation may improve without silently redefining analysis domains or growing
into a partial RAW-conversion pipeline.

P3 deliberately precedes Workflow & Session Productivity. Session persistence and
workflow features should capture stable image-analysis semantics rather than
encode compatibility or RAW-display rules that are about to change.

## Program sequence

`P3-0 → P3-A → P3-B → P3-C → P3-D → P3-E`

| Order | Slice | Purpose | Status / prerequisite |
|---|---|---|---|
| 0 | P3-0 roadmap transition | Close/archive P2 and establish P3 | Complete — PR #21 |
| 1 | P3-A Difference domain extension | Gray + mixed-bit Difference semantics | Complete — PR #22 |
| 2 | P3-B RAW native/display semantics | Native RAW authority + black-anchored display gain | Implementation/review follow-up complete; current-head revalidation/merge pending |
| 3 | P3-C RAW visualization/inspection | Improve RAW observability without processed-RAW scope creep | Next after P3-B merge |
| 4 | P3-D RAW profile management | Reusable profiles and profile suggestion workflow | After P3-C |
| 5 | P3-E integration hardening | Cross-analysis regressions, docs, Windows characterization | After P3-D |

Each implementation slice starts from the latest merged prerequisite on `main`.
The exact branch/PR breakdown may be refined by the P3 orchestra, but the semantic
ordering above is authoritative unless a new owner decision changes it.

## Why P3 and P4 are reordered

The previous roadmap placed Workflow & Session Productivity before RAW work. The
order remains changed because image semantics should be stable before persistent
sessions save or restore them.

P3-A closed the immediate Difference gap. P3-B now defines RAW native/display
ownership. Remaining P3 work should focus on RAW visualization and profile
usability while preserving native sample authority. Demosaic is not automatically
required merely because Bayer RAW is supported.

Therefore:

- **P3 remains Image Semantics & RAW Processing.**
- **P4 remains Workflow & Session Productivity.**
- P5–P7 retain their previous order.

## P3-0 — Program transition

Status: Complete — merged as PR #21 at
`5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`.

This slice was documentation only and established the P3 program.

## P3-A — Difference Gray / Mixed Bit-Depth Support

Status: Complete — merged as PR #22 at
`769588bf869847da844cfc0b77c008023d8b048b`.

The production contract now supports:

- `GRAY ↔ GRAY`;
- `RGB/RGBA ↔ RGB/RGBA`;
- Bayer ↔ Bayer only when the CFA pattern matches;
- explicit rejection of cross-family, dimension, and CFA mismatches;
- native code-domain Difference for equal effective bit depths;
- independent effective-full-scale normalization to `[0,1]` for mixed bit depths;
- `%FS` threshold semantics in normalized Difference;
- bounded float32 normalized computation/metrics;
- explicit cached Difference-domain metadata;
- compact Scope/Domain UI and short validation states.

RAW black/white metadata, display transforms, preview values, demosaic output, and
implicit RGB→Gray conversion do not participate in P3-A normalization. That
separation remains an invariant for later P3 slices.

## P3-B — RAW Native & Display Semantics

Status: Implementation and independent-review follow-up are complete on
`feature/p3-b-raw-native-display-semantics`. Owner/local Windows quality
validation passed on pre-review HEAD
`e7c1cc2ea0b08f43d3d513f6712035aa828eec5b`; the current review-fix HEAD requires
revalidation before merge.

### Implemented native-source authority

- Decoded RAW samples remain authoritative and unchanged in
  `ImageDocument.source`.
- Existing `black_level` and `white_level` profile metadata remain supported with
  their current JSON/schema compatibility.
- A schema-valid four-value `black_level` on a GRAY profile remains accepted.
  Its global/GRAY gain anchor preserves the pre-P3-B rule `min(black_level)`;
  Bayer mosaics still use all four CFA-specific anchors and split CFA planes use
  their named anchor.
- Black/white metadata and RAW display gain do not alter pixel inspection,
  Statistics, Histogram, Line Profile source data, Split Channels, source
  residency accounting, or P3-A Difference.
- P3-A Difference remains governed by effective bit depth/full scale and its own
  native/normalized domain contract.
- Display-only gain changes do not bump `ImageDocument.generation` or redefine
  cache identity.

### Implemented viewer display semantics

At 1× display gain, RAW display maps the native code domain
`0..((1 << bit_depth) - 1)` to the uint8 preview range. Black is not implicitly
subtracted and white is not promoted to display full scale.

When display gain is greater than 1×, gain is anchored at black level:

```text
display = black + gain * (native - black)
```

The transform uses float32 promoted arithmetic so values below black remain
negative/residual values rather than unsigned underflow. Clipping is deferred to
the final uint8 display conversion. Bayer R/Gr/Gb/B black tuples are applied by
CFA parity for RGGB/GRBG/GBRG/BGGR without constructing a processed source.

P3-B does not apply `white_level` to either 1× native display or gained display.
White level remains stored RAW-profile metadata for future explicit processing.

### Implemented UI/runtime boundary

- Product startup installs one compact toolbar `RAW Gain` control with
  1×/2×/4×/8×/16× choices.
- The gain state is application-session-only and is not stored in `RawProfile`,
  workspace QSettings, or application Settings; schema remains v5.
- Single and Multi View viewers consume the same session gain. Ordinary non-RAW
  images are not transformed by RAW gain.
- Gain changes reuse resident native source; they do not request RAW reloads.
- Gain >1 preview regeneration uses the existing shared numerical `QThreadPool`
  rather than doing the full-frame transform synchronously on the UI thread.
- Viewer request/task/document/source/generation/gain identity rejects stale async
  results before presentation replacement.
- The derived gained preview is viewer presentation only. `ImageDocument.preview`
  remains the replaceable 1× base preview and `ImageDocument.source` remains the
  analysis authority.
- Hidden RAW viewers release any gain>1 derived buffer by restoring the canonical
  1× document preview. When shown again they regenerate the current session gain
  on demand, preventing hidden Multi View tiles from retaining persistent UHD
  gained-preview allocations.

### P3-B regression coverage added

Coverage was added for:

- RAW10/12/14 effective-full-scale display mapping;
- black and white not becoming 1× display endpoints;
- preview equality when only `white_level` differs;
- known-value `B + G * (X - B)` arithmetic and below-black underflow prevention;
- final-only clipping;
- RGGB/GRBG/GBRG/BGGR CFA-specific black anchors and unchanged native mosaics;
- schema-valid GRAY four-value Black Level through JSON profile load and
  deterministic legacy `min(tuple)` gain anchoring;
- native pixel/Statistics/Histogram/Line Profile/Split Channels values;
- same-bit and mixed-bit P3-A Difference independence;
- source generation/residency accounting independence;
- non-RAW display regression;
- RAW load preservation and current profile metadata;
- Single/Multi View gain behavior, default 1×, session-only state, and stale gain
  request rejection;
- 6→2→6 Multi View lifecycle release/regeneration of viewer-local gained previews;
- existing Bayer and RAW chart characterization call sites under the explicit
  display API.

The Chat implementation agent intentionally does **not** execute pytest, ruff,
mypy, docs checker, pip check, or packaging commands. Owner/local Windows ran the
full quality gate successfully on pre-review HEAD
`e7c1cc2ea0b08f43d3d513f6712035aa828eec5b`. Because the independent-review
follow-up changes production code and tests, the current review-fix HEAD requires
owner/local revalidation before merge.

### P3-B exclusions retained

P3-B does **not** add:

- demosaic;
- white balance;
- CCM/color-space conversion;
- gamma/tone mapping as a new product feature;
- optical-black estimation or automatic pedestal detection;
- a processed-RAW document or analysis mode;
- a new Difference domain;
- RAW profile management/suggestion;
- session persistence;
- Settings schema expansion;
- preload/residency policy redesign;
- installer/signing work;
- broad MainWindow/toolbar redesign.

## P3-C — RAW Visualization & Inspection Improvements

P3-C remains intentionally re-scoped away from committed demosaic integration.

Its purpose is to improve RAW observability after P3-B establishes display-domain
semantics. Candidate work includes:

- clearer gain/exposure inspection controls or presentation;
- optional clipping/highlight/shadow visualization where useful for engineering
  inspection;
- improved native Bayer-channel/mosaic inspection;
- viewer affordances that remain explicitly display-only.

Do not change Statistics/Histogram/Line Profile/Difference domains merely because
the viewer presentation changes.

Demosaic is deferred unless the owner later approves a coherent processed-preview
scope. Before implementing it, explicitly decide whether white balance, CCM,
tone/gamma, black/white normalization, and analysis interactions belong in the
same feature. A bare demosaic that creates misleading color output is not a P3-C
requirement.

## P3-D — RAW Profile Management

Build the reusable profile workflow after RAW native/display semantics are stable.

Target areas:

- reusable profile storage/selection;
- clear profile identity/versioning;
- safe edit/duplicate/delete behavior if introduced;
- profile suggestion based on deterministic metadata/size evidence;
- no silent profile application when evidence is ambiguous;
- compatibility with existing JSON profile migration and exact-size policy.

## P3-E — Integration & Hardening

Close P3 over the completed Difference/RAW semantics.

- Cross-check native/normalized Difference and RAW native/display ownership.
- Characterize representative Gray/RGB/Bayer/RAW and bit-depth combinations.
- Preserve P2 residency/preload/diagnostics contracts.
- Verify Statistics/Histogram/Line Profile/Difference/Split Channels regressions.
- Complete Windows characterization and durable P3 documentation.
- Do not add unrelated workflow/session or deferred processed-RAW features as part
  of phase closure.

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
- source dtype/channel meaning explicit and overflow-safe arithmetic;
- native decoded RAW remains recoverable and authoritative even when viewer-only
  presentation transforms are active.

A P3 slice may extend display metadata or explicit derived representations, but it
must not collapse source residency, Difference cache, previews, or future
processed RAW data into one ambiguous memory owner.

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
- native C/C++ optimization without profiling evidence;
- demosaic, white balance, CCM, or tone/gamma processing merely to make RAW look
  camera-rendered.

These remain later roadmap or owner-approved work.

## Validation policy

For runtime slices, focused tests and the full repository contract remain the
completion standard:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Execution agents must not claim these passed unless their output was actually
observed. For P3-B, owner/local Windows observed the full gate passing on
`e7c1cc2ea0b08f43d3d513f6712035aa828eec5b`; the independent-review follow-up
requires the same gate to be rerun on the new HEAD before merge.

## P3 exit criteria

P3 is complete when:

- P3-A Gray/mixed-bit Difference semantics remain stable;
- RAW native samples are authoritative and viewer display transforms cannot be
  confused with analysis-domain processing;
- black-anchored RAW display gain is deterministic and regression-covered;
- RAW visualization improvements, if added, remain explicitly display-only;
- reusable profile management/suggestion is deterministic and safe;
- existing P2 runtime/resource/diagnostic contracts remain stable;
- full automated and agreed Windows validation pass;
- durable docs describe the final Difference and RAW domains without ambiguity.

Demosaic is not required for P3 completion under the current owner decision.

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
