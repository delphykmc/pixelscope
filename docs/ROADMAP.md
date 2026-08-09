# Roadmap

## Delivered baseline

### P0/P1 product foundation

- PNG/BMP/JPEG and profile-described RAW loading with native source preservation.
- Ordered selection, registered one-to-six-folder navigation, synchronized
  cursor/range/ROI/line state, and fixed one-to-six-image layouts.
- Statistics, Histogram, Line Profile, Difference, Split Channels, structured
  status, and persisted workspace/Plots state.
- RAW10/12/14 plus unpacked uint8/uint16 decoding with deterministic fixtures.
- P1-D/P1-E/P1-F workspace-polish program completed as PR #10–#12.
- Historical P1 plan:
  `docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`.

### P2 — Runtime Foundation, Settings & Performance

P2 is complete.

Completed sequence:

`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`

- P2-0 merged as PR #13.
- P2-A1 identity/resources merged as PR #14.
- P2-A2 typed settings/runtime integration merged as PR #15.
- P2-B byte-budgeted decoded-source residency merged as PR #16.
- P2-C bounded next-position preload merged as PR #17.
- P2-D deterministic runtime diagnostics merged as PR #18.
- P2-E RUNNING preload foreground reuse merged as PR #19.
- P2-F performance characterization/hardening merged as PR #20 at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.

P2 closes with settings schema v5, independent source/Difference memory budgets,
protected soft-budget source residency, `+1` one-position max-one preload,
RUNNING preload authority promotion, deterministic sanitized diagnostics, and
hardware-independent correctness/resource/lifecycle merge gates.

Historical P2 plan:
`docs/exec-plans/completed/p2-runtime-foundation-settings-performance.md`.

## Revised forward sequence

The previous roadmap placed Workflow & Session Productivity before RAW work. The
order is revised so image-analysis semantics stabilize before persistent sessions
and workflow state are built around them.

`P3 Image Semantics & RAW Processing`
→ `P4 Workflow & Session Productivity`
→ `P5 Remote IQA Platform`
→ `P6 Identity, Access & Remote Operations`
→ `P7 Release Engineering & Distribution`

## P3 — Image Semantics & RAW Processing

P3-0 is complete as PR #21 at
`5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`; implementation slices start from
the latest merged P3 prerequisite.

### P3-0 — Program transition — Complete

- Merged as PR #21 at `5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`.
- Archived P2 completion state, established the revised P3/P4 order, and created
  the active P3 execution plan.
- Documentation only.

### P3-A — Difference Gray / Mixed Bit-Depth Support — Complete

P3-A merged as PR #22 at
`769588bf869847da844cfc0b77c008023d8b048b`.

The completed contract is:

- Gray ↔ Gray;
- RGB/RGBA ↔ RGB/RGBA;
- Bayer ↔ Bayer only with the same CFA pattern;
- reject cross-family, size-mismatch, and CFA-mismatch cases;
- no implicit RGB→Gray/luma conversion;
- same effective bit depth uses native code-domain Difference;
- different effective bit depths normalize each source by its own effective
  full-scale code value to `[0,1]` and use `%FS` threshold semantics;
- RAW black/white metadata and display transforms do not define P3-A Difference
  normalization.

P3-A also delivers explicit Gray channel support, bounded float32 mixed-bit
Difference/metrics, cache domain metadata, compact Scope/Domain UI, and short
validation reasons with detailed tooltips.

### P3-B — RAW Native & Display Semantics

Keep PixelScope centered on engineering inspection rather than silently turning
RAW loading into a RAW-conversion pipeline.

- Native decoded RAW remains the authoritative source and is not modified by
  black/white metadata or viewer controls.
- Keep existing `black_level` and `white_level` RAW-profile metadata.
- At 1× display gain, the viewer shows the native RAW code domain using effective
  bit depth/full-scale for display mapping rather than subtracting black level.
- When display gain is applied, anchor the transform at black level:
  `display = black + gain * (native - black)`.
- Bayer profiles may use their existing R/Gr/Gb/B black levels as channel-specific
  display anchors.
- White level remains available as saturation/display metadata and for future
  explicit processing, but must not redefine native pixel values.
- Pixel inspection, Statistics, Histogram, Line Profile source data, Split
  Channels, and P3-A Difference remain native-domain operations.
- Gain is display-only; it must not mutate `ImageDocument.source` or silently
  create a new analysis domain.
- Preserve black/white metadata for future explicit tone-map or processed-RAW
  features without adding those processing stages in P3-B.

### P3-C — RAW Visualization & Inspection Improvements

Improve RAW observability without introducing a partial RAW converter.

Candidate scope:

- make RAW display gain/exposure inspection clearer and easier to use;
- optional clipping/highlight or shadow visualization where it materially helps
  sensor/ISP inspection;
- improve Bayer-channel/native-mosaic visualization and inspection affordances;
- preserve native source authority and explicit display-only semantics;
- avoid changing Statistics/Histogram/Line Profile/Difference domains merely
  because the viewer presentation changes.

Demosaic is no longer a committed P3-C deliverable. A future demosaic feature
must first define the intended processed-preview boundary and whether white
balance, color correction, tone/gamma, and related metadata are in scope. Until
that product need is explicit, P3 should not grow into a partial RAW-conversion
pipeline.

### P3-D — RAW Profile Management

- Reusable profile storage/selection.
- Stable profile identity/versioning.
- Safe profile edit/reuse workflow.
- Deterministic profile suggestion with no silent ambiguous application.
- Preserve existing JSON migration and exact-size policy.

### P3-E — Integration & Hardening

- Cross-check native/normalized Difference with RAW native/display ownership.
- Characterize representative Gray/RGB/Bayer/RAW and bit-depth combinations.
- Preserve P2 residency/preload/diagnostics contracts.
- Complete automated/Windows validation and durable P3 documentation.

P3 excludes persistent sessions, remote/authentication work, release engineering,
broad MainWindow/shortcut rewrites, speculative preload-policy expansion, native
optimization without profiling evidence, and demosaic/white-balance/color/tone
processing unless separately approved by the owner.

## P4 — Workflow & Session Productivity

This is the former P3 scope, intentionally moved after image/RAW semantics.

- Persistent comparison sessions.
- Recent Files/Folders.
- Saved ROI manager.
- Arbitrary-angle line sampling.
- Alpha overlay.
- Additional productivity and export workflows.

## P5 — Remote IQA Platform

- Remote submission and result workflow.
- Server/job API.
- GPU worker.
- Artifact, heatmap, and result comparison.

## P6 — Identity, Access & Remote Operations

- Login and SSO.
- Token/credential lifecycle.
- Permission and access policy.
- Operational administration.

## P7 — Release Engineering & Distribution

- Exactly PyInstaller 5.7 `onedir`.
- Portable ZIP.
- Inno Setup.
- Clean-PC smoke testing.
- Signing.
- Update strategy.
- Repeatable release process.

## Deferred optimization outside the phase sequence

P2 characterization left several evidence-driven optimization candidates that do
not currently justify reopening the runtime foundation:

- preload concurrency one versus two;
- directional/bidirectional or deeper preload;
- CPU/I/O aggressiveness controls;
- broader resource-policy Settings exposure;
- process-level memory/profiler telemetry.

These should be scheduled only when later profiling or user-visible latency gives
a concrete reason to change the established P2 policy.
