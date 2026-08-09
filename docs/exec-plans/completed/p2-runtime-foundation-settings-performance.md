# Execution plan: P2 — Runtime Foundation, Settings & Performance

Status: Complete
Owner: repository owner + P2 orchestration agents
Completed: 2026-08-09
Final merge baseline: `9c66629f6392971b8c52ac9dff27b16166cf9829`

## Goal

Establish application identity, typed settings, byte-budgeted source residency,
bounded preload, deterministic diagnostics, running-preload foreground reuse,
and final performance hardening without a broad `MainWindow` rewrite.

## Completed sequence

`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`

| Slice | Outcome | PR |
|---|---|---|
| P2-0 | Program setup and roadmap transition | #13 |
| P2-A1 | Application identity and packaged resources | #14 |
| P2-A2 | Typed settings and runtime integration | #15 |
| P2-B | Byte-budgeted decoded-source residency | #16 |
| P2-C | Bounded next-position preload | #17 |
| P2-D | Deterministic runtime diagnostics | #18 |
| P2-E | Running preload promotion / foreground reuse | #19 |
| P2-F | Performance characterization and hardening | #20 |

P2-F merged as PR #20 at
`9c66629f6392971b8c52ac9dff27b16166cf9829`, completing P2.

## Durable runtime contracts

- `ApplicationSettings` is the frozen persisted settings model;
  `SettingsRepository` owns schema/default/migration/reset behavior and
  `QSettingsAdapter` owns raw application-preference keys.
- Settings schema v5 owns RAW confirmation/exact-size behavior, optional default
  Open/Export folders, Difference Threshold/Gain, Difference Map Cache,
  Decoded Source Memory, and preload enablement.
- Difference Map Cache defaults to 128 MiB. Decoded Source Memory defaults to
  256 MiB. The two budgets remain independent and startup-only.
- Decoded source residency accounts exact native `ImageDocument.source.nbytes`
  and uses deterministic protected LRU soft-budget semantics.
- Folder Position navigation is atomic over one to six registered distinct
  folders and shares one pure planner with preload prediction.
- Preload remains `plan(+1)` only, exactly one Folder Position deep, with a
  dedicated max-one pool and foreground priority.
- An exact matching RUNNING preload may transfer logical authority to foreground
  while the same physical worker/decode continues. Promotion is not thread
  migration and does not change pool sizes.
- Cancellation is advisory; token/generation/request identity remains the
  correctness authority for late asynchronous results.
- Runtime diagnostics are frozen, deterministic, bounded, sanitized, and
  observation-only. The sole user surface is **Help > Copy Diagnostics**.
- Statistics/Histogram numerical requests are idempotent when source identity,
  generation, layout/Bayer semantics, ROI, and histogram specification are
  unchanged.

## P2-F closure evidence

P2-F replaced hardware-dependent elapsed-time merge gates with deterministic
correctness/resource/lifecycle assertions while retaining timing only as
observational output.

Representative characterization covers:

- FHD RGB uint8;
- FHD grayscale uint16;
- UHD Bayer uint16 profile-described RAW;
- existing real 4K RGB and RGGB10-u16 fixtures;
- source residency and Difference-cache pressure;
- completed preload reuse, RUNNING promotion, normal-load fallback, rapid
  navigation, and stale-result rejection;
- Settings schema/default/migration/reset contracts;
- observation-only diagnostics;
- Windows navigation, RAW/Bayer, Difference, Statistics/Histogram, Line Profile,
  Split Channels, Settings restart behavior, and support-copy workflows.

Owner/local Windows automated validation and the agreed manual matrix were
reported passing before PR #20 merge. Independent review found no remaining
production/test blocker. Windows CI remains deferred until a stable
PySide6/pytest-qt/offscreen runner contract is demonstrated; packaging CI remains
P7 work.

## Deferred after P2

Evidence-driven optimization candidates remain separate from the completed P2
runtime contract:

- preload concurrency one versus two;
- directional/bidirectional or deeper prediction;
- CPU/I/O aggressiveness and broader resource-policy controls;
- process-level memory accounting or profiler-style telemetry.

The current Difference capability also retains a semantic limitation that is
intentionally moved to the next technical program rather than reopening P2:
GRAY comparison and mixed-bit-depth normalized Difference are not yet supported
through the standard Difference workflow.

## Transition

The next active program is **P3 — Image Semantics & RAW Processing**. Its first
implementation slice stabilizes Difference compatibility/domain semantics before
RAW black/white-level and demosaic processing are expanded. The former P3
Workflow & Session Productivity program moves to P4 so session/workflow features
are built on the stabilized image-analysis semantics.
