# Execution plan: P1-D workspace completion and compatibility cleanup

Status: Active  
Owner: repository owner + coding agent  
Branch/PR: to be created after PR #7  
Last updated: 2026-08-06

## Goal

Complete the remaining Plots workspace behavior and remove obsolete Multi View
arrangement compatibility state. Completion is observable when floating Plots
restores its own geometry, title-bar double-click toggles maximize/restore,
Esc/Shift+Esc labels and behavior are exact, selected-tab persistence remains
covered, and no arrangement choice/key remains.

## Scope

### In scope

- Independent floating Plots geometry persistence.
- Floating title-bar double-click maximize/restore.
- `Clear ROI` and `Clear Line Profile` action naming/shortcut tests.
- Regression coverage for existing selected bottom-tab persistence.
- Removal/migration of the fixed-arrangement registry, field, actions, and
  `ui/multiview_arrangement` setting.
- Current-state, architecture, decision, UI, and user-guide updates.

### Out of scope

- Preferences UI or runtime cache-budget changes.
- Byte-budgeted decoded-image residency or preload.
- RAW demosaic/normalization/profile suggestion.
- Packaging, installer, update checking, or remote GPU work.
- Broad MainWindow refactoring unrelated to persistence/compatibility cleanup.

## Current state

- `src/pixelscope/app/main_window.py` persists main geometry, dock state,
  splitters, layout, Plots visibility, compatibility arrangement, and
  `analysis/bottom_tab`.
- `src/pixelscope/ui/plots_dock_title.py` has explicit Float/Dock,
  Maximize/Restore, and Hide buttons but no title-bar double-click handler.
- Esc invokes `_escape_action()`, which only calls `clear_roi()`, while the Edit
  label still says `Clear ROI / Restore Grid`.
- `src/pixelscope/ui/multi_compare_view.py` exposes
  `_FixedArrangementRegistry` only to accept one legacy value.
- PR #6 and #8 completed Histogram and Line Profile behavior.

## Invariants and constraints

- CPython 3.10, PySide6 6.4.2, and current public shortcuts remain fixed.
- Docked maximize must restore to the original dock area.
- Floating maximize must restore to its previous floating geometry.
- Hide/show must not silently re-dock or reset the selected tab.
- Esc clears ROI only; Shift+Esc clears the shared line only.
- Fixed one-to-six-image geometry and six-source Difference restoration must not
  regress.
- Persistence tests must isolate `QSettings` and not depend on test order.

## Proposed design

1. Give Plots floating geometry an explicit QSettings key using
   `saveGeometry()`/`restoreGeometry()` only while floating.
2. Route title-bar double-click through the same maximize/restore state machine
   as the explicit button.
3. Rename the Edit action without changing the callback or shortcut.
4. Add focused persistence and interaction tests before removing compatibility
   state.
5. Replace arrangement-dependent startup/reset/restore paths with the single
   fixed policy, then remove the compatibility registry/key.
6. Keep changes in small commits or slices so persistence and compatibility
   cleanup can be reviewed independently.

## Implementation slices

1. **Persistence characterization**
   - Files/components: `main_window.py`, existing UI smoke/persistence tests
   - Observable result: selected tab and current dock state have explicit
     regression coverage before changes
   - Tests: fresh/saved/invalid settings and reset behavior

2. **Floating geometry and double-click**
   - Files/components: `main_window.py`, `plots_dock_title.py`
   - Observable result: floating geometry and maximize/restore survive
     hide/show and restart
   - Tests: floating, docked, maximized, restored, title double-click

3. **Shortcut and terminology cleanup**
   - Files/components: `main_window.py`, toolbar/action tests, user guide
   - Observable result: Edit menu says `Clear ROI`; Esc and Shift+Esc affect
     only their intended selections
   - Tests: ROI-only and line-only state transitions

4. **Arrangement compatibility removal**
   - Files/components: `main_window.py`, `multi_compare_view.py`, layout/reset
     tests
   - Observable result: no arrangement menu/action/field/setting remains; fixed
     layouts and six-source Difference restore are unchanged
   - Tests: one-to-six geometry, focus promotion, legacy setting tolerance or
     deletion, reset, six-source restore

5. **Durable documentation**
   - Files/components: current state, architecture, decisions, roadmap, UI
     status, user guide
   - Observable result: P1-D is marked complete and later backlog remains
     separate
   - Tests: `scripts/check_docs.py`

## Validation plan

- Targeted UI tests for Plots persistence, title interactions, shortcuts, fixed
  layouts, and six-source Difference restoration.
- `scripts/check_docs.py`.
- Full pytest, Ruff check, Ruff format check, mypy, and pip check.
- Manual Windows checks for floating geometry, double-click, hide/show,
  maximize/restore, restart, and reset.
- No packaging tools.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Qt saves stale floating geometry | restart tests and manual multi-monitor check | save only valid floating geometry and clamp/validate restore |
| Double-click conflicts with drag | focused event test and manual title-bar check | call existing toggle path and accept only left-button double-click |
| Removing arrangement state breaks restore | layout and six-source tests | characterize behavior first; remove in separate slice |
| QSettings tests become order-dependent | randomized/full-suite run | isolate organization/app names and clear settings per test |
| Dock state and geometry overwrite each other | fresh/saved/reset matrix | define ownership and restore order explicitly |

## Progress log

- 2026-08-06: Audited PR #1–#9 excluding #7 and current `main`.
- 2026-08-06: Confirmed P1-B reference selection and selected-tab persistence
  are already complete.
- 2026-08-06: Confirmed Esc behavior is correct but its label is stale.
- 2026-08-06: Confirmed arrangement storage is compatibility-only.
- 2026-08-06: Separated Preferences/residency/RAW/distribution work from P1-D.

## Completion summary

Fill in when complete:

- Delivered behavior:
- Changed files:
- Validation results:
- Manual checks:
- Remaining limitations:
- Follow-up issues:
- Durable docs updated:
