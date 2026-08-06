# Execution plan: P1-D to P1-F workspace polish

Status: Complete — P1-D and P1-E merged; P1-F implemented and automatically validated in PR #12
Owner: repository owner + coding agent
Branch/PR: one scoped PR per phase after PR #7
Last updated: 2026-08-07

## Goal

Complete the remaining workspace interaction, Plots persistence, and legacy
layout cleanup without combining unrelated risk into one oversized change.

The work is split into independently mergeable phases:

- P1-D defines primary-image ordering for every Multi View and makes Split
  Channels transitions visually atomic.
- P1-E completes Plots dock persistence and shortcut terminology.
- P1-F removes obsolete fixed-arrangement compatibility state after the
  preceding behavior is protected by tests.

## Phase status

| Phase | Status | Pull request |
|---|---|---|
| P1-D — Multi View ordering and atomic Split transitions | Merged and validated | PR #10 |
| P1-E — Plots workspace completion | Merged and validated | PR #11 |
| P1-F — fixed-layout compatibility cleanup | Implemented; automated validation complete; manual Windows validation pending | PR #12 |

## P1-D — completed behavior

P1-D owns user-visible behavior in `multi_compare_view.py`, tile headers,
shared toolbar icons, and targeted Multi View UI tests.

### Primary-image interaction

- Regular Multi Views containing two through six displayed documents expose a
  primary-image flag.
- The first displayed image is the implicit primary when no valid explicit
  primary exists.
- Selecting another primary promotes that document to the first raster tile.
- Files selection order, logical document IDs, and logical slot badges do not
  change when display order changes.
- Two-, four-, and six-view layouts retain equal-sized geometry; only display
  order changes.
- Three- and five-view layouts retain the enlarged first, primary tile.
- Primary controls use layout-neutral terminology:
  - unchecked: `Set as primary image`;
  - checked: `Primary image`;
  - status tip: `Set as primary image and move it to the first tile`.
- Transient `CHANNEL_*` Split Channels documents do not expose primary flags
  because their component order is fixed.
- Control visibility follows the realized Multi View workspace lifecycle and
  does not leak into hidden workspaces.

### Atomic Split Channels transition

`MultiCompareView.set_documents()` determines the target document count,
applies final geometry and visibility, and only then binds replacement content.
Updates are suppressed only for the replacement batch and one final repaint is
requested afterward.

This removes the observable Bayer/RGB split-grid to unsplittable-GRAY
upper-left intermediate frame while preserving loading-placeholder and stale
result behavior.

### Shortcut ownership cleanup

Page Up/Page Down folder-pair navigation remains owned by MainWindow application
shortcuts. `ImageViewer` no longer calls MainWindow folder-navigation methods by
name; viewer key handling routes through the registered shortcut instead.

### Preserved invariants

- `_multi_display_order` remains the display-order owner.
- `_focus_document_id` remains the internal explicit primary/reference identity
  while valid.
- Files selection order and document IDs remain unchanged.
- Viewer objects and synchronized ranges are preserved during promotion.
- Difference priority and enlarged three-/five-view primary-first geometry are
  retained.
- Single View header navigation does not rebuild the workspace.
- Split Channels component order remains fixed.
- Six-source restore behavior is not changed by P1-D.

### P1-D validation evidence

The repository owner confirmed after the final shortcut and documentation
cleanup that:

- `scripts/check_docs.py` passes;
- the full pytest suite passes;
- Ruff lint and formatting checks pass;
- mypy passes for `src`;
- `pip check` passes;
- folder-pair Page Up/Page Down navigation works from the Files view and visible
  image tiles;
- paired folders advance and retreat together;
- first/last boundary navigation leaves selection unchanged and reports the
  expected `No previous image` / `No next image` status;
- primary flags and first-tile promotion behave correctly in regular Multi
  Views;
- Split Channels transitions no longer expose the transient old-grid frame.

P1-D has no pending validation item.

## P1-E — Plots and Statistics workspace completion

P1-E owns Plots dock lifecycle, QSettings persistence, shortcut cleanup,
interaction gestures, and the final Statistics workspace presentation.

### Delivered behavior

- Floating Plots geometry persists independently from main-window geometry.
- Floating title-bar double-click uses the same maximize/restore path as the
  explicit title-bar button.
- `MainWindow` creates `Clear ROI` directly and owns workspace-reset
  integration through `PlotsDockTitleBar.clear_persisted_geometry()`.
- Esc clears ROI only; Shift+Esc clears the shared line only.
- Ctrl+drag creates ROI, Shift+drag creates Line Profile, and Alt+drag creates
  neither.
- The selected Histogram/Line Profile tab persists through
  `analysis/bottom_tab`.
- Statistics uses numbered Region, Images, and Channel statistics sections.
- Region presents aligned Scope and Bounds rows and disables Active ROI until
  a valid shared ROI exists.
- Images reports bit depth and analyzed Pixels; long folder-qualified labels
  remain one row with middle elision and full tooltips.
- Channel statistics uses visual image-group separators without synthetic rows
  or changes to copy/CSV behavior.
- Analysis activity collapses after successful completion.

### Preserved invariants

- P1-D primary ordering, Page Up/Page Down shortcut ownership, fixed Multi View
  geometry, Split Channels ordering, and atomic replacement remain intact.
- Hide/show does not silently re-dock Plots or reset its selected tab.
- Floating maximize restores the previous normal floating geometry; docked
  maximize restores to the original dock area.
- Statistics row order, selection, clipboard copy, and CSV semantics remain
  stable.
- Persistence tests isolate QSettings and do not depend on test order.

### Validation evidence

The repository owner confirmed after all P1-E fixes that the full pytest suite,
Ruff lint and formatting checks, mypy, documentation contract, and `pip check`
pass. Manual Windows validation confirms Plots persistence and maximize/restore,
exact ROI/line gestures and clear shortcuts, Active ROI lifecycle, Statistics
grouping and separators, and long image-label elision.

## P1-F — fixed-layout compatibility cleanup

P1-F is implemented as compatibility cleanup only; it adds no layout choice and
does not redesign MainWindow.

### Delivered behavior

- Removed `_FixedArrangementRegistry`, `MULTIVIEW_ARRANGEMENTS`,
  `FIXED_MULTIVIEW_ARRANGEMENT`, and `TOP_FOCUS_ARRANGEMENT`.
- Removed `MultiCompareView.arrangement`, `set_arrangement()`, and all MainWindow
  arrangement fields, menu/action state, setter, and render calls.
- Removed arrangement from `SixImageDiffRestoreState` and its capture/restore
  path.
- Startup no longer reads `ui/multiview_arrangement`; save no longer writes it;
  Reset Workspace Layout removes the legacy key when present.
- `_fixed_geometry()` remains the sole one-to-six Multi View geometry policy.

### Preserved behavior

- Exact one-to-six placements and row/column stretch values.
- P1-D primary ordering, Files selection order, logical slot badges, viewer
  reuse, synchronized ranges, Split Channels replacement, and folder navigation.
- P1-E Plots persistence, gestures, selected-tab persistence, Statistics, and
  workspace reset behavior.
- Exact six-source Difference restoration of layout mode, primary, active
  document, page/current indices, display order, logical slots, and view state.

### Tests and validation

- Added focused coverage for geometry, primary ordering, legacy settings,
  obsolete symbol absence, reset behavior, and six-source restoration.
- The repository owner confirmed the full CPython 3.10 automated validation
  contract passes: documentation checks, the complete pytest suite, Ruff lint
  and format checks, mypy for `src`, and `pip check`.
- Manual Windows checks remain pending for visual and timing-sensitive behavior.

## Scope exclusions

- Preferences UI or runtime cache-budget changes.
- Byte-budgeted decoded-image residency or preload.
- RAW demosaic, normalization, or profile suggestion.
- Packaging, installer, update checking, or remote GPU work.
- Broad MainWindow refactoring unrelated to these phase contracts.
- P1-E or P1-F implementation inside PR #10.

## Standard validation for each phase

Run from the repository root with the pinned CPython 3.10 environment:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
```

Manual Windows checks remain required for visual/timing-sensitive behavior.
No packaging tools are part of these phases.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Primary semantics unexpectedly change analysis/reference priority | reference-selection tests | retain `_focus_document_id` and existing priority rules |
| Reordering even views changes selection or logical IDs | ordering tests | mutate only `_multi_display_order` |
| Split batching introduces blank or stale frames | transition-order and placeholder tests | apply final geometry first and suppress updates only for the batch |
| Page Up/Page Down behavior depends on a hidden viewer | visible-widget shortcut tests and manual check | keep navigation in application shortcuts and target realized widgets |
| Qt saves stale floating geometry | restart tests and manual multi-monitor check | save only valid floating geometry and validate restore |
| Double-click conflicts with title dragging | targeted event test and manual title-bar check | reuse the existing maximize/restore state machine |
| Removing arrangement state breaks restore | layout and six-source tests | perform P1-F only after P1-D/E coverage is merged |
| QSettings tests become order-dependent | full-suite run | isolate settings and clear state per test |

## Phase dependencies and review boundaries

1. **P1-D:** merged in PR #10; establishes primary-order semantics, Page Up/Page Down ownership, and atomic Split transitions.
2. **P1-E:** merged and validated in PR #11; completes Plots, gesture, and Statistics workspace behavior.
3. **P1-F:** implemented and automatically validated in PR #12; removes compatibility state after P1-D/P1-E behavior is mechanically protected.

Each phase must remain independently mergeable and must not carry deferred code
for a later phase.

## Progress log

- 2026-08-06: Audited PR #1–#9 excluding #7 and current `main`.
- 2026-08-06: Confirmed P1-B reference selection and selected-tab persistence
  are complete.
- 2026-08-06: Confirmed Esc behavior is correct but its label is stale.
- 2026-08-06: Confirmed arrangement storage is compatibility-only.
- 2026-08-06: Added even-view primary ordering requirement.
- 2026-08-06: Identified document-before-layout ordering as the Bayer-to-GRAY
  Split transition flicker mechanism.
- 2026-08-06: Split the remaining workspace work into P1-D, P1-E, and P1-F.
- 2026-08-06: Completed P1-D primary flags, implicit/explicit primary ordering,
  equal even-view geometry, and atomic Split replacement in PR #10.
- 2026-08-06: Removed direct ImageViewer-to-MainWindow method-name coupling for
  folder-pair Page Up/Page Down handling.
- 2026-08-06: Repository owner confirmed the full standard validation suite and
  manual Windows behavior checks pass.
- 2026-08-06: Updated durable product/user/architecture documentation to use
  primary-image terminology.

- 2026-08-06: PR #10 merged into `main` at `e79f9bd15085d9a492b67f3c9beb81e897ff0a0b`.
- 2026-08-06: Completed P1-E Plots persistence, gesture/shortcut cleanup, Statistics workspace polish, and action-ownership cleanup in PR #11.
- 2026-08-06: Repository owner confirmed the complete P1-E standard validation suite and manual Windows behavior checks pass.
- 2026-08-06: PR #11 merged into `main`; P1-F started from main commit `175905105a1679ff0142ddcb3e2acaca28d1da64`.
- 2026-08-06: Removed arrangement compatibility runtime/QSettings/restore state and added focused P1-F regression coverage.
- 2026-08-07: Repository owner confirmed the full P1-F automated validation contract passes; manual Windows checks remain pending.
- 2026-08-07: No completed-plan directory exists, so this plan remains at the required active path with `Status: Complete`.

## P1-D completion summary

- **Delivered behavior:** primary flags and first-tile ordering for regular
  two-to-six-image Multi Views; atomic Split Channels replacement; shortcut
  ownership cleanup.
- **Changed areas:** Multi View layout/content binding, tile header styling and
  icons, image-viewer shortcut routing, durable documentation, and targeted UI
  regression tests.
- **Validation:** full standard validation suite confirmed locally by the
  repository owner; targeted manual Windows checks confirmed.
- **Remaining limitations:** none identified within P1-D scope.
- **Follow-up:** P1-E and P1-F remain separate scoped phases.
- **Durable docs:** `USER_GUIDE.md`, `PRODUCT_SPEC.md`, `ARCHITECTURE.md`,
  `CURRENT_STATE.md`, `ROADMAP.md`, this execution plan, and PR #10.


## P1-E completion summary

- **Delivered behavior:** independent floating Plots geometry; title-bar
  maximize/restore; direct MainWindow ownership of Clear ROI and workspace
  reset; Ctrl/Shift gesture pairing with Alt removal; numbered and ROI-aware
  Statistics presentation; bit-depth/pixel metadata; single-line image labels;
  image-group separators; collapsible activity state.
- **Changed areas:** `main_window.py`, `plots_dock_title.py`,
  `image_viewer.py`, `comparison_analysis_panel.py`, focused UI tests, and
  durable user/execution-plan documentation.
- **Validation:** full pytest, Ruff check and format check, mypy,
  documentation contract, and `pip check` confirmed locally by the repository
  owner; manual Windows behavior checks confirmed.
- **Remaining limitations:** mixed-dimension Full image bounds wording and
  richer native-range diagnostics are deferred; multi-monitor placement remains
  a future robustness check.
- **Follow-up:** P1-F is implemented separately on updated `main`.
- **Durable docs:** `docs/USER_GUIDE.md`, this execution plan, and PR #11.


## P1-F completion summary

- **Delivered behavior:** fixed Multi View geometry now has no arrangement
  registry, runtime field, menu/action, QSettings read/write path, or six-source
  restore dependency.
- **Changed areas:** `multi_compare_view.py`, `main_window.py`, focused UI tests,
  and durable state/roadmap documentation.
- **Validation:** full documentation, pytest, Ruff lint/format, mypy, and
  `pip check` contract confirmed locally by the repository owner; manual Windows
  checks remain pending.
- **Remaining limitations:** only the explicitly deferred backlog; no new phase
  is introduced.
- **Durable docs:** `CURRENT_STATE.md`, `ROADMAP.md`,
  `ui/implementation_status.md`, this execution plan, and the P1-F PR.
