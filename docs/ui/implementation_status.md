# PixelScope UI/performance iteration status

Snapshot date: 2026-08-08
Current merged runtime baseline: PR #15 merge commit
P2-B branch base: `1869764a74b01cebebaf8fa915b11a2a696be6cb`

## Completed iterations

| Phase/PR | State | Main result |
|---|---|---|
| P0-A / #1 | Complete | Fixed Multi View layouts and primary behavior foundation |
| P0-B / #2 | Complete | Difference byte LRU and chunked metrics |
| P0-C / #3 | Complete | Toolbar/primary icons and action states |
| P0-D / #4 | Complete | Split loading, disabled menus, Difference ordering |
| P1-A / #5 | Complete | Files, Statistics, responsive headers |
| P1-B1 / #6 | Complete | Histogram modes and plot text |
| P1-B2 / #8 | Complete | Line Profile reference and legends |
| P1-C / #9 | Complete | RAW profile workflow and MIPI decoding |
| P1-D / #10 | Complete | Primary ordering, atomic Split transitions, folder navigation |
| P1-E / #11 | Complete | Plots persistence, gestures, Statistics workspace |
| P1-F / #12 | Complete | Fixed-layout compatibility cleanup |
| P2-A1 / #14 | Complete | Application identity and packaged resources |
| P2-A2 / #15 | Complete | Typed Settings schema v3 and runtime integration |
| P2-B | Active | Byte-budgeted decoded-source residency and schema v4 |

## Current UI behavior

### Files and workspace

- Files tree exposes File and Type with loading/resident/error indicators.
- Ordered selection drives fixed one-to-six-image layouts.
- Difference selectors are the comparison-pair authority.
- Split Channels supports RGB/Bayer placeholders and fixed component order.
- Every regular two-to-six-image Multi View exposes primary behavior. Promotion
  preserves Files order, logical badges, viewer identity, and synchronized range.
- Two/four/six views remain equal; three/five enlarge the first tile.
- `_fixed_geometry()` is the sole Multi View geometry contract; no arrangement
  menu, runtime field, or persisted setting remains.

### Analysis

- Statistics supports Full image and Active ROI with stable copy/CSV behavior.
- Histogram exposes explicit bins and Count/Normalized/Log count modes.
- Line Profile exposes compact legends and explicit Difference reference.
- Difference uses a 128 MiB native-map byte LRU with diagnostics.
- Floating Plots geometry and selected tab persist; title double-click
  maximizes/restores.
- Esc clears ROI; Shift+Esc clears Line Profile; Ctrl+drag creates ROI;
  Shift+drag creates Line Profile; Alt+drag creates neither.

### RAW

- Profile dialog separates storage/container/depth/endian/alignment.
- Unpacked uint8/uint16 and MIPI RAW10/12/14 are implemented.
- JSON load/save, migration, confirmation preference, and same-path reload are
  implemented.
- Bayer remains native mosaic analysis; demosaic is not implemented.

## Completed P1 workspace-polish program

P1-D, P1-E, and P1-F are complete as PR #10, #11, and #12. The former Split
transition cause analysis is retained in the completed execution-plan history
rather than as active remediation guidance:

`docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`

Automated validation for P1-F was recorded by the repository owner. P1-F manual
Windows evidence was not re-verified by P2-0.

## Current performance/settings boundary

Implemented now:

- Difference byte-budget LRU and diagnostics.
- Byte-budgeted native decoded-source LRU with a 256 MiB default.
- Soft-budget protection for visible, selected, active/analysis, Difference-pair,
  and active load-target sources.
- Exact native `source.nbytes` accounting and minimal residency diagnostics.
- Schema-v4 General / Files / Performance Settings with distinct Decoded Source
  Memory and Difference Map Cache startup budgets.
- Canonical application icon/resource foundation and immutable
  `PerformanceSettings` startup injection.
- Bounded normal-load and numeric worker pools.

Not implemented yet:

- One-group-ahead preload.
- Runtime diagnostics UI/snapshot and Copy Diagnostics.

P2-C preload and P2-D diagnostics remain the next runtime slices. P2-B behavior
must not be treated as merged release behavior until its phase PR is merged.
