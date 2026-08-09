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

P3 starts from completed P2 at
`9c66629f6392971b8c52ac9dff27b16166cf9829`.

### P3-0 — Program transition

- Archive P2 completion state.
- Establish the revised P3/P4 order.
- Create the active P3 execution plan.
- Documentation only.

### P3-A — Difference Gray / Mixed Bit-Depth Support

Correct and extend the existing Difference capability before RAW processing
semantics expand.

Planned compatibility:

- Gray ↔ Gray;
- RGB/RGBA ↔ RGB/RGBA;
- Bayer ↔ Bayer only with the same CFA pattern;
- reject cross-family, size-mismatch, and CFA-mismatch cases;
- no implicit RGB→Gray/luma conversion.

Planned domain policy:

- same effective bit depth: preserve native code-domain Difference;
- different effective bit depths: normalize each source by its own full-scale
  code value to `[0,1]`, then calculate Difference;
- normalized threshold is expressed as `%FS`;
- RAW black/white levels and display transforms do not define this normalization.

Implementation targets include explicit Gray channel support, bounded float32
mixed-bit Difference/metrics, cache domain metadata, compact Scope/Domain UI, and
short validation reasons with detailed tooltips.

### P3-B — RAW Processing Semantics

- Explicit black-level subtraction and white-level/full-scale handling.
- Native decoded source versus processed RAW representation boundary.
- Overflow-safe clipping/normalization.
- Derived-data cache/generation/invalidation rules.
- Preserve P3-A Difference full-scale semantics as a separate contract.

### P3-C — Demosaic Integration

- Explicit demosaic algorithm/interface boundary.
- Native Bayer versus demosaiced RGB viewing/analysis semantics.
- Worker/cache integration without replacing native source authority.
- Explicit Statistics/Histogram/Line Profile/Difference behavior.

### P3-D — RAW Profile Management

- Reusable profile storage/selection.
- Stable profile identity/versioning.
- Safe profile edit/reuse workflow.
- Deterministic profile suggestion with no silent ambiguous application.
- Preserve existing JSON migration and exact-size policy.

### P3-E — Integration & Hardening

- Cross-check native/normalized Difference with RAW processing ownership.
- Characterize representative Gray/RGB/Bayer/RAW and bit-depth combinations.
- Preserve P2 residency/preload/diagnostics contracts.
- Complete automated/Windows validation and durable P3 documentation.

P3 excludes persistent sessions, remote/authentication work, release engineering,
broad MainWindow/shortcut rewrites, speculative preload-policy expansion, and
native optimization without profiling evidence.

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
