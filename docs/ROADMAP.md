# Roadmap

## Delivered baseline

### P0/P1 product foundation

- PNG/BMP/JPEG and profile-described RAW loading with native source preservation.
- Ordered selection, registered one-to-six-folder Page Up/Page Down navigation, synchronized
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

Sequential dependency:
`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`.

- **P2-0 — Program setup and roadmap transition:** close P1 durable
  documentation, establish this P2 program, reconcile current state, docs only.
- **P2-A1 — Application identity and resource foundation:** canonical icon,
  packaged-safe resources, reproducible derivatives, source-run application
  identity, and package-data verification. Complete; merged as PR #14.
- **P2-A2 — Settings foundation and runtime integration:** typed settings,
  QSettings adapter/migration, Settings dialog, restart-required/reset behavior,
  RAW policies, analysis defaults, and Difference-cache startup injection.
  Complete; merged as PR #15.
- **P2-B — Byte-budgeted decoded-source residency:** native-source byte
  accounting, protected LRU, soft budget, eviction/reload, invalidation, setting,
  and diagnostics API. Complete; merged as PR #16.
- **P2-C — Bounded next-position preload:** complete; merged as PR #17 at
  `812982dacdecca155f7b53ab42ef2bd9fba68a77`. It owns one registered Folder
  Position ahead, normal-load priority, bounded ownership, stale
  cancellation/drop, request validation, ordinary residency retention, the
  startup setting, and bounded counters.
- **P2-D — Runtime diagnostics and failure visibility:** complete; merged as
  PR #18 at `a7b4ddf62af95e86b9d9e38a4328cf9572226114`. It provides deterministic,
  sanitized source/cache/worker/preload/stale/failure snapshots plus the single
  on-demand **Help > Copy Diagnostics** support surface. No live diagnostics UI
  or text-file export.
- **P2-E — Running Preload Promotion / Foreground Reuse:** complete; merged as
  PR #19 at `7ee7aec2980baeef9d511f3db5c71f89fa319a64`. An exact matching RUNNING
  preload that becomes foreground-required transfers logical authority to the
  foreground while reusing the same worker/decode. Preload remains `+1` only,
  exactly one Folder Position deep, fixed concurrency one, normal pool max two,
  and preload pool max one.
- **P2-F — Performance Characterization & Phase Hardening:** active on
  `feature/p2-f-performance-hardening`; final P2 slice. It audits the completed
  P2 contracts, characterizes representative FHD RGB uint8, FHD grayscale
  uint16, UHD Bayer uint16/RAW and existing 4K fixtures, removes hardware/load-
  dependent elapsed-time merge gates, reviews source/Difference resource policy,
  preload/promotion lifecycle, diagnostics, and Windows feasibility, and closes
  durable P2 documentation without adding a new large feature.

P2-F preserves settings schema v5 and the established preload/resource policy.
Wall-clock measurements are observational evidence only; deterministic
correctness, resource, request-identity, worker-ownership, and stale-result
invariants are the merge gates. Any later concurrency, bidirectional/deeper
prediction, CPU/I/O aggressiveness, or resource-policy expansion requires a
separate evidence-driven optimization slice.

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
