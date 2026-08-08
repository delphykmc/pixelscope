# Roadmap

## Delivered baseline

### P0/P1 product foundation

- PNG/BMP/JPEG and profile-described RAW loading with native source preservation.
- Ordered selection, folder-pair Page Up/Page Down navigation, synchronized
  cursor/range/ROI/line state, and fixed one-to-six-image layouts.
- Statistics, Histogram, Line Profile, Difference, Split Channels, structured
  status, and persisted workspace/Plots state.
- Byte-budgeted `DifferenceMapCache` with a 128 MiB default, LRU eviction,
  chunked native metrics, and `used_bytes`/`budget_bytes`/`entry_count`
  diagnostics.
- Byte-budgeted decoded-source residency with exact native-source accounting,
  protected LRU soft-budget behavior, reload, invalidation, and minimal
  diagnostics.
- RAW profile workflow, unpacked uint8/uint16 alignment/endian support, MIPI
  RAW10/12/14, Bayer mosaic analysis, JSON migration, and deterministic fixtures.
- Fixed Multi View geometry, primary-image behavior, exact six-source Difference
  restoration, floating Plots persistence/maximize, ROI/Line gestures, and
  Statistics workspace contracts.

### Workspace-polish completion

- P1-D merged as PR #10.
- P1-E merged as PR #11.
- P1-F merged as PR #12 at
  `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`.
- The historical execution plan is retained at
  `docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`.

## P2 — Runtime Foundation, Settings & Performance

Sequential dependency: `P2-0 → P2-A → P2-B → P2-C → P2-D → P2-E`.

- **P2-0 — Program setup and roadmap transition:** close P1 durable
  documentation, establish this P2 program, reconcile current state, docs only.
- **P2-A — Application identity and Settings foundation:** canonical icon and
  packaged-safe resources, typed settings, QSettings adapter/migration,
  Settings dialog, restart-required/reset behavior, and Difference-cache startup
  injection.
- **P2-B — Byte-budgeted decoded-source residency:** replace the fixed-count
  policy with native-source byte accounting, protected LRU, soft budget,
  eviction/reload, invalidation, setting, and diagnostics API. Implemented on
  `feature/p2-b-source-residency-budget`; validation/merge are in progress.
- **P2-C — Bounded next-group preload:** one folder group ahead, normal-load
  priority, bounded ownership, stale cancellation/drop, request validation,
  budget-aware retention, setting, and counters.
- **P2-D — Runtime diagnostics and failure visibility:** deterministic/redacted
  source/cache/worker/preload/stale/failure snapshot, Copy Diagnostics, and
  optional text export.
- **P2-E — Performance characterization and phase hardening:** integration,
  settings migration/default tests, FHD/UHD and image-format matrices,
  low-budget/oversize/rapid-navigation characterization, deterministic smoke
  tests, Windows CI feasibility, and P2 completion docs. No new large feature.

P2 excludes persistent sessions, Recent Files/Folders, saved ROI management,
arbitrary-angle sampling, alpha overlay, RAW processing expansion, remote IQA,
authentication, packaging/signing/update checking, broad MainWindow/shortcut
rewrites, and unprofiled native optimization.

## P3 — Workflow & Session Productivity

- Persistent comparison sessions.
- Recent Files/Folders.
- Saved ROI manager.
- Arbitrary-angle line sampling.
- Alpha overlay.
- Additional productivity and export workflows.

## P4 — RAW Processing & Profile Management

- Demosaic.
- Black/white-level processing.
- Reusable profile management.
- Profile suggestion.

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
