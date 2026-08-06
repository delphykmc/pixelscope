# Execution plan: P1-D to P1-F workspace polish

Status: Active — P1-D complete; P1-E and P1-F pending  
Owner: repository owner + coding agent  
Branch/PR: one focused PR per phase after PR #7  
Last updated: 2026-08-06

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
| P1-D — Multi View ordering and atomic Split transitions | Complete; validated locally; pending merge | PR #10 |
| P1-E — Plots workspace completion | Pending | Separate focused PR |
| P1-F — fixed-layout compatibility cleanup | Pending | Separate focused PR |

## P1-D — completed behavior

P1-D owns user-visible behavior in `multi_compare_view.py`, tile headers,
shared toolbar icons, and focused Multi View UI tests.

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
- Three- and five-view layouts retain the existing enlarged first tile.
- Primary controls use layout-neutral terminology:
  - unchecked: `Set as primary image`;
  - checked: `Primary image`;
  - status tip: `Set as primary image and move it to the first tile`.
- Transient `CHANNEL_*` Split Channels documents do not expose primary flags
  because their component order is fixed.
- Control visibility follows the realized Multi View workspace lifecycle and
  does not leak into hidden workspaces.

### Atomic Split Channels transition

`MultiCompareView.set_documents()` now determines the target document count,
applies final geometry and visibility, and only then binds replacement content.
Updates are suppressed only for the replacement batch and one final repaint is
requested afterward.

This removes the observable Bayer/RGB split-grid to unsplittable-GRAY
upper-left intermediate frame while preserving loading-placeholder and stale
result behavior.

### Shortcut ownership cleanup

PageUp/PageDown folder-pair navigation remains owned by MainWindow application
shortcuts. `ImageViewer` no longer calls MainWindow folder-navigation methods by
name; viewer key handling routes through the registered shortcut instead.

### Preserved invariants

- `_multi_display_order` remains the display-order owner.
- `_focus_document_id` remains the explicit primary/reference identity while
  valid.
- Files selection order and document IDs remain unchanged.
- Viewer objects and synchronized ranges are preserved during promotion.
- Difference priority and existing three-/five-view focus geometry are retained.
- Single View header navigation does not rebuild the workspace.
- Split Channels component order remains fixed.
- Six-source restore behavior is not changed by P1-D.

### P1-D validation evidence

The repository owner confirmed after the final shortcut cleanup that:

- the full automated test suite passes;
- folder-pair PageUp/PageDown navigation works from the Files view and visible
  image tiles;
- paired folders advance and retreat together;
- first/last boundary navigation leaves selection unchanged and reports the
  expected `No previous image` / `No next image` status;
- primary flags and first-tile promotion behave correctly in regular Multi
  Views;
- Split Channels transitions no longer expose the transient old-grid frame.

The final documentation change still requires `scripts/check_docs.py` to be run
from the pinned project environment before PR #10 is marked ready.

## P1-E — Plots workspace completion

This phase owns dock lifecycle, QSettings persistence, and shortcut cleanup.

### Required behavior

- Persist floating Plots geometry independently from main-window geometry.
- Add title-bar double-click maximize/restore for floating Plots.
- Rename `Clear ROI / Restore Grid` to `Clear ROI`.
- Preserve Esc as ROI-only and Shift+Esc as line-only.
- Preserve selected-tab persistence through `analysis/bottom_tab`.

### Implementation slices

#### P1-E slice 1 — persistence characterization

- Files/components: `main_window.py`, existing UI smoke/persistence tests
- Observable result: selected tab and current dock state have explicit
  regression coverage before restoration behavior changes
- Tests: fresh, saved, invalid, legacy, reset, and restart settings

#### P1-E slice 2 — floating geometry and double-click

- Files/components: `main_window.py`, `plots_dock_title.py`
- Observable result: floating geometry and maximize/restore survive hide/show
  and restart
- Tests: floating, docked, maximized, restored, and title double-click

#### P1-E slice 3 — shortcut and terminology cleanup

- Files/components: `main_window.py`, action tests, user guide
- Observable result: Edit menu says `Clear ROI`; Esc and Shift+Esc affect only
  their intended selections
- Tests: ROI-only, line-only, and simultaneous ROI/line states

### P1-E invariants

- Docked maximize restores to the original dock area.
- Floating maximize restores to the previous floating geometry.
- Hide/show does not silently re-dock or reset the selected Plots tab.
- Esc clears ROI only; Shift+Esc clears the shared line only.
- Persistence tests isolate QSettings and do not depend on test order.

## P1-F — fixed-layout compatibility cleanup

This phase removes obsolete state only after P1-D and P1-E behavior is covered.

### Required behavior

- Remove `_FixedArrangementRegistry`, arrangement fields/actions, and the
  `ui/multiview_arrangement` QSettings key.
- Replace arrangement-dependent startup, reset, and six-image Difference
  restore paths with the single fixed-layout policy.
- Ignore or safely discard legacy arrangement values without exposing a new
  layout choice.

### Preserved behavior

- Fixed one-to-six-image geometry.
- Primary ordering established by P1-D.
- Active document and synchronized ranges.
- Six-source Difference restoration.
- Current startup and workspace reset outcomes except for removal of obsolete
  arrangement state.

### Tests

- One-to-six fixed geometry.
- Primary ordering and logical slot preservation.
- Legacy setting handling.
- Startup and reset behavior.
- Six-source Difference restoration.

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
| PageUp/PageDown behavior depends on a hidden viewer | visible-widget shortcut tests and manual check | keep navigation in application shortcuts and target realized widgets |
| Qt saves stale floating geometry | restart tests and manual multi-monitor check | save only valid floating geometry and validate restore |
| Double-click conflicts with title dragging | focused event test and manual title-bar check | reuse the existing maximize/restore state machine |
| Removing arrangement state breaks restore | layout and six-source tests | perform P1-F only after P1-D/E coverage is merged |
| QSettings tests become order-dependent | full-suite run | isolate settings and clear state per test |

## Phase dependencies and review boundaries

1. **P1-D:** complete in PR #10; establishes primary-order semantics and atomic
   Split transitions.
2. **P1-E:** next; independent dock/persistence work with a narrower test
   matrix.
3. **P1-F:** last; removes compatibility state after preceding behavior is
   mechanically protected.

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
  folder-pair PageUp/PageDown handling.
- 2026-08-06: Repository owner confirmed the final automated suite and manual
  Windows behavior checks pass.

## P1-D completion summary

- **Delivered behavior:** primary flags and first-tile ordering for regular
  two-to-six-image Multi Views; atomic Split Channels replacement; shortcut
  ownership cleanup.
- **Changed areas:** Multi View layout/content binding, tile header styling and
  icons, image-viewer shortcut routing, and focused UI regression tests.
- **Validation:** full automated suite confirmed locally by the repository
  owner; targeted manual Windows checks confirmed.
- **Remaining limitations:** final documentation checker must be rerun after
  this roadmap update.
- **Follow-up:** P1-E and P1-F remain separate focused phases.
- **Durable docs:** this active execution plan and PR #10 description.
