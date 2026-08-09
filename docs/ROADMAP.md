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
the latest merged P3 prerequisite. P3 roadmap replanning merged as PR #23 at
`4c7d1bbbb4476134f76a204578098d35a03feca2`.

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
- RAW Black/White metadata and display transforms do not define P3-A Difference
  normalization.

P3-A also delivers explicit Gray channel support, bounded float32 mixed-bit
Difference/metrics, cache domain metadata, compact Scope/Domain UI, and short
validation reasons with detailed tooltips.

### P3-B — RAW Native & Display Semantics — Implementation Complete

P3-B is implemented on `feature/p3-b-raw-native-display-semantics`. Owner/local
Windows quality validation passed on
`424144215b1df97c71a84ddca79a17bfccb1feef`, including the generic Display Gain
core, RAW Gain runtime behavior, and `+` / `-` stepping. Final independent
re-review found one merge blocker on that validated head: window-wide gain
shortcuts intercepted the Files tree's native `+` / `-` expand/collapse keys. The
review follow-up scopes gain shortcuts to the image-presentation subtree and adds
real key-routing coverage; latest-head revalidation and merge remain pending.

Delivered contract:

- Native decoded RAW remains the authoritative source and is not modified by
  Black/White metadata or viewer controls.
- Existing `black_level` and `white_level` RAW-profile metadata remain schema- and
  JSON-compatible; Settings stays at schema v5.
- At 1× display gain, RAW maps native code `0..((1 << bit_depth) - 1)` to the
  preview range. Black is not subtracted and White is not promoted to full scale.
- P3-B introduces a **generic anchor-based display-gain core**:
  `display = anchor + gain * (source - anchor)`.
- The generic core is presentation-only and is not RAW-metadata-aware. RAW adapters
  supply the anchor policy: scalar Black for RAW Gray, channel-specific R/Gr/Gb/B
  Black for Bayer where available, and the legacy `min(tuple)` anchor for
  schema-compatible GRAY tuple profiles.
- The core naturally supports `anchor=0` and operation on channel views so later
  ordinary Gray/RGB/RGBA presentation can reuse it without a second gain engine.
- P3-B **activates the gain UI/runtime only for RAW**. Ordinary Gray/RGB/RGBA
  images remain unchanged in this slice.
- Gain/range mapping uses float32 fused affine processing where possible. It does
  not create a full-size Bayer Black map or promote full-frame gain math to
  float64.
- `white_level` remains metadata only for P3-B display; effective full scale is
  the RAW display-range authority.
- Pixel inspection, Statistics, Histogram, Line Profile source data, Split
  Channels, source residency, and P3-A Difference remain native-domain operations.
- The compact session-local `RAW Gain` control provides 1×/2×/4×/8×/16×. The same
  gain is shared across visible RAW tiles in Single/Multi View; ordinary images
  are unaffected.
- The `+` / `-` gain commands are scoped to the image-presentation subtree with
  `WidgetWithChildrenShortcut`. Files keeps Qt-native `+` / `-` folder
  expand/collapse whether RAW Gain is enabled or disabled.
- The viewer keeps a 1× fast path using the canonical document preview. Gain >1
  uses resident native source and the shared numerical worker pool; stale async
  results are rejected without source reload/decode, generation changes,
  residency-policy changes, or Difference-cache invalidation.
- Hidden viewers release gain>1 derived presentation buffers and regenerate the
  current gain when shown again.

P3-B intentionally adds no ordinary-image gain UI, demosaic, white balance, CCM,
tone mapping, processed RAW document, processed analysis mode, persistence,
Settings migration, or resource-policy redesign.

### P3-C — RAW Visualization & Inspection Improvements + Display Gain Extension

P3-C reuses the P3-B generic display-gain core rather than creating a second
ordinary-image gain implementation. It also reuses the P3-B presentation-scoped
keyboard-command policy rather than adding a window-global shortcut owner.

Committed Display Gain scope:

- extend viewer-only gain to ordinary Gray and RGB using `anchor=0`;
- support RGBA presentation with the same RGB gain while preserving alpha;
- use the user-facing term **Display Gain** or **Gain**; do not label this feature
  **Exposure**;
- preserve native Gray/RGB/RGBA source arrays and keep Statistics, Histogram,
  Line Profile, Difference, residency, and cache semantics independent of gain;
- retain a 1× identity/fast path and deterministic final clipping;
- retain viewer-scoped `+` / `-` stepping and preserve Files-tree native
  expand/collapse behavior;
- test 1× identity, clipping, Gray, RGB, RGBA alpha preservation, analysis
  independence, command/control synchronization, and Files-tree key routing.

Additional RAW visualization/inspection candidates remain:

- make RAW Gain and clipping state clearer for engineering inspection;
- optional highlight/shadow clipping visualization where materially useful;
- improve Bayer-channel/native-mosaic visualization and inspection affordances;
- keep viewer affordances explicitly display-only.

Demosaic remains deferred. A future demosaic feature must first define the
processed-preview boundary and whether white balance, color correction,
tone/gamma, and related metadata belong in the same feature. Until that product
need is explicit, P3 should not grow into a partial RAW-conversion pipeline.

### P3-D — RAW Profile Management

- Reusable profile storage/selection.
- Stable profile identity/versioning.
- Safe profile edit/reuse workflow.
- Deterministic profile suggestion with no silent ambiguous application.
- Preserve existing JSON migration and exact-size policy.

### P3-E — Integration & Hardening

- Cross-check native/normalized Difference with RAW native/display ownership.
- Characterize representative Gray/RGB/RGBA/Bayer/RAW and bit-depth combinations.
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

P2/P3 characterization leaves several evidence-driven optimization candidates
that do not currently justify reopening the runtime foundation:

- preload concurrency one versus two;
- directional/bidirectional or deeper preload;
- CPU/I/O aggressiveness controls;
- broader resource-policy Settings exposure;
- process-level memory/profiler telemetry;
- coalescing/debounce/cancellable chunking for rapid large-RAW gain stepping if
  profiling demonstrates material latency or transient memory pressure;
- native/SIMD gain optimization beyond the current float32 fused affine path.

These should be scheduled only when later profiling or user-visible latency gives
a concrete reason to change the established runtime policy.
