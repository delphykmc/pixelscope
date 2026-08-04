# Phase P1-B — Plots

## Scope

P1-B refines Histogram, Line Profile, and the floating/docked Plots workspace without changing image loading, Difference computation, or packaging.

## Implementation progress

- Histogram implementation and targeted tests are prepared on `chatgpt/p1b-plots`.
- Line Profile reference selection is next.
- Floating/docked Plots persistence and Esc behavior follow after Line Profile.

## Histogram

- Add a `Bins` selector with `Auto`, `256`, `1024`, and `4096`.
- Define `Auto` as `min(2^bit_depth, 4096)`.
- Keep the native x-range tied to the real code range even when the displayed histogram uses fewer bins.
- Keep UI histogram binning separate from exact metric/statistics precision.
- Extend Y modes to `Count`, `Normalized`, and `Log count`.

## Line Profile

- Show a `Reference` selector only when Y mode is `Difference from reference`.
- Resolve the default reference in this order:
  1. pinned/focus document
  2. active document
  3. first displayed document
- Keep reference selection stable while the referenced document remains available.
- Retain compact image/channel legends and adaptive identity markers.

## Floating and docked Plots

- Persist the last selected plot tab.
- Persist floating geometry independently from the main window geometry.
- Support title-bar double-click maximize/restore for floating Plots.
- `Esc` remains `Clear ROI`; it must not restore or re-dock Plots.
- `Shift+Esc` remains `Clear Line Profile`.
- Rename the Edit command from `Clear ROI / Restore Grid` to `Clear ROI`.

## Validation

- Add targeted tests for histogram bin selection, log count, reference resolution, plot-tab persistence, floating geometry, title double-click behavior, and Esc handling.
- Run the full pytest, Ruff, format, mypy, and pip-check suite before PR creation.
