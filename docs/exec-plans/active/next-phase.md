# Execution plan: P3 — Image Semantics & RAW Processing

Status: Active
Owner: repository owner + P3 orchestration agents
Last updated: 2026-08-09
Current merged P3 baseline: P3-A / PR #22 merge commit
`769588bf869847da844cfc0b77c008023d8b048b`

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
| 2 | P3-B RAW native/display semantics | Native RAW authority + black-anchored display gain | Active next slice — start from latest `main` |
| 3 | P3-C RAW visualization/inspection | Improve RAW observability without processed-RAW scope creep | After P3-B |
| 4 | P3-D RAW profile management | Reusable profiles and profile suggestion workflow | After P3-C |
| 5 | P3-E integration hardening | Cross-analysis regressions, docs, Windows characterization | After P3-D |

Each implementation slice starts from the latest merged prerequisite on `main`.
The exact branch/PR breakdown may be refined by the P3 orchestra, but the semantic
ordering above is authoritative unless a new owner decision changes it.

## Why P3 and P4 are reordered

The previous roadmap placed Workflow & Session Productivity before RAW work. The
order remains changed because image semantics should be stable before persistent
sessions save or restore them.

P3-A closed the immediate Difference gap. The remaining P3 work should now focus
on RAW viewing and profile usability while preserving native sample authority.
Demosaic is not automatically required merely because Bayer RAW is supported.

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

### Objective

Define the minimum RAW-viewing semantics PixelScope needs as a sensor/ISP
engineering viewer without turning native RAW loading into an implicit processing
pipeline.

### Native-source authority

- Decoded RAW samples remain authoritative and unchanged in
  `ImageDocument.source`.
- Existing `black_level` and `white_level` profile metadata remain supported.
- Black/white metadata do not silently alter pixel inspection, Statistics,
  Histogram, Line Profile source data, Split Channels, or P3-A Difference.
- P3-A Difference remains governed by effective bit depth/full-scale and its own
  native/normalized domain contract.

### Viewer display semantics

At 1× display gain, RAW display must represent the native code domain rather than
implicitly subtracting black level. Effective bit depth/full scale remains the
normal native display range authority.

When display gain is greater than 1×, gain is anchored at black level:

```text
display = black + gain * (native - black)
```

This keeps the sensor black baseline stationary while magnifying positive and
negative residuals around it. For Bayer RAW, the existing R/Gr/Gb/B black-level
metadata may be used as channel-specific anchors where the preview path can do so
without changing native source data.

White level remains metadata for saturation/display reference and future explicit
processing. It must not redefine the stored native sample values.

Clipping needed for the final 8-bit preview is a display concern only. Do not
write clipped/gained values back into the native source or expose them as if they
were native analysis samples.

### Scope boundary

P3-B may refactor `DisplayTransform` or RAW-preview plumbing so the above contract
is explicit and testable. Keep algorithms outside Qt widgets and preserve the
existing background-load/threading boundaries.

P3-B does **not** add:

- demosaic;
- white balance;
- CCM/color-space conversion;
- gamma/tone mapping;
- optical-black estimation or automatic pedestal detection;
- a processed-RAW analysis mode;
- a new Difference domain;
- settings/schema expansion unless a persistence need is demonstrated and
  separately approved.

Black/white metadata are retained so future explicit processing can use them
without forcing that processing into P3-B.

### P3-B acceptance targets

Deterministic coverage should establish at least:

- RAW load preserves native sample values regardless of black/white metadata;
- 1× viewer display uses native RAW code semantics;
- black-anchored gain follows `B + G * (X - B)` with overflow-safe arithmetic;
- values below black remain meaningful through the gain transform until final
  display clipping;
- Bayer per-channel black anchors behave deterministically where supported;
- changing display gain does not change native pixel inspection/Statistics/
  Histogram/Difference semantics;
- white level remains available as metadata without silently becoming a source
  normalization rule;
- existing RAW10/12/14 and unpacked uint8/uint16 loading contracts regress cleanly;
- P2 source residency/preload/diagnostics ownership is unchanged.

## P3-C — RAW Visualization & Inspection Improvements

P3-C is intentionally re-scoped away from committed demosaic integration.

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
observed. Owner/local validation remains authoritative when the implementation
agent is not operating in the owner's configured Windows virtual environment.

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
