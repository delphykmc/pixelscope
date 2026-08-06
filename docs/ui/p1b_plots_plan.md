# Phase P1-B — Plots status

## Scope

P1-B refines Histogram, Line Profile, and the floating/docked Plots workspace
without changing image loading, Difference computation, or packaging.

## Completed

### Histogram — PR #6

- Auto/256/1024/4096 bins.
- Auto defined as `min(2^bit_depth, 4096)`.
- Native code-value x range.
- Count, Normalized, and Log count modes.
- Compact coordinate-first tooltip/title behavior.
- Deterministic bit-depth fixtures and focused tests.

### Line Profile — PR #8

- Reference selector shown only for Difference-from-reference.
- Initial priority: focused/pinned, active, first displayed.
- Stable explicit reference while available.
- Exact-zero reference curve.
- Compact image-ID/channel legends and larger identity markers.

### Existing persistence confirmed

- The selected Histogram/Line Profile tab is already saved and restored through
  `analysis/bottom_tab`.

## Remaining work moved to P1-D

- Persist floating geometry independently from main-window geometry/dock state.
- Support title-bar double-click maximize/restore for floating Plots.
- Rename `Clear ROI / Restore Grid` to `Clear ROI`.
- Preserve Esc as Clear ROI and Shift+Esc as Clear Line Profile.
- Add explicit regression tests for existing selected-tab persistence and the
  remaining floating/double-click/shortcut behavior.

The active execution plan is
[`../exec-plans/active/next-phase.md`](../exec-plans/active/next-phase.md).
