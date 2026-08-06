# Execution plan: P1-D to P1-F workspace polish

Status: Active  
Owner: repository owner + coding agent  
Branch/PR: one focused PR per phase after PR #7  
Last updated: 2026-08-06

## Goal

Complete the remaining workspace interaction, Plots persistence, and legacy
layout cleanup without combining unrelated risk into one oversized change.
Completion is observable when every Multi View supports pinned first-tile
ordering, Split Channels transitions are visually atomic, Plots state restores
predictably, shortcut terminology is exact, and obsolete arrangement state is
removed without changing fixed one-to-six-image geometry.

## Phase split

### P1-D — Multi View ordering and atomic Split transitions

This phase owns user-visible behavior in `main_window.py`,
`multi_compare_view.py`, tile headers, and Multi View UI tests.

- Show the pin control for every Multi View containing two or more displayed
  documents, including 2-, 4-, and 6-view layouts.
- Define a pinned document as the primary display document:
  - it is promoted to the first raster position for every Multi View count;
  - in 3- and 5-view layouts, the first position is also the enlarged focus
    tile;
  - in 2-, 4-, and 6-view layouts, geometry remains equal-sized and only order
    changes.
- Preserve logical selection order, document IDs, viewer reuse, synchronized
  ranges, Difference ordering, and six-source restore state.
- Replace focus-only wording such as `Pin as focus tile` with wording that is
  correct in all layouts, such as `Pin to first tile`.
- Make Split Channels layout/content replacement atomic, especially the
  Bayer-four-channel to unsplittable-GRAY-one-view transition.

### P1-E — Plots workspace completion

This phase owns dock lifecycle, QSettings persistence, and shortcut cleanup.

- Persist floating Plots geometry independently from main-window geometry.
- Add title-bar double-click maximize/restore for floating Plots.
- Rename `Clear ROI / Restore Grid` to `Clear ROI`.
- Preserve Esc as ROI-only and Shift+Esc as line-only.
- Add explicit regression coverage for the already implemented selected-tab
  persistence through `analysis/bottom_tab`.

### P1-F — fixed-layout compatibility cleanup

This phase removes obsolete state only after P1-D and P1-E behavior is covered.

- Remove `_FixedArrangementRegistry`, arrangement fields/actions, and the
  `ui/multiview_arrangement` QSettings key.
- Replace arrangement-dependent startup, reset, and six-image Difference
  restore paths with the single fixed-layout policy.
- Preserve one-to-six geometry, pinned ordering, active document, ranges, and
  six-source Difference restoration.

## Scope exclusions

- Preferences UI or runtime cache-budget changes.
- Byte-budgeted decoded-image residency or preload.
- RAW demosaic/normalization/profile suggestion.
- Packaging, installer, update checking, or remote GPU work.
- Broad MainWindow refactoring unrelated to these phase contracts.

## Current state and code analysis

### Pin/order behavior

- `MultiCompareView.set_documents()` initially permits the focus control when
  more than one document is present.
- `_arrange_viewers()` then overrides that state and exposes the control only
  for counts 3 and 5.
- `MainWindow._set_focus_document()` already promotes the requested document
  through `_multi_display_order` without changing ordered selection.
- Therefore the missing even-view behavior is primarily a visibility and
  terminology restriction, but tests must also define the pinned state as
  persistent primary ordering rather than enlarged geometry.

### Split Channels transition

The Bayer-to-GRAY visual jump is explained by the current update order:

1. Split mode keeps Multi View capacity at four.
2. `_split_display_documents()` returns four Bayer channel documents but only
   the original document for GRAY.
3. `MultiCompareView.set_documents()` binds the new GRAY document while the
   previous 2x2 geometry is still active.
4. Only after document binding does `_arrange_viewers(1)` move the first viewer
   to the full single-view geometry.
5. Qt can paint between steps 3 and 4, exposing a transient upper-left tile
   before the final full-size viewer.

The optimization must change this ordering rather than merely accepting the
flicker as valid behavior.

### Plots and compatibility

- MainWindow persists main geometry, dock state, splitters, layout, Plots
  visibility, compatibility arrangement, and `analysis/bottom_tab`.
- `PlotsDockTitleBar` has explicit Float/Dock, Maximize/Restore, and Hide
  buttons but no title double-click path.
- Esc already calls only `clear_roi()`, while the menu label is stale.
- `_FixedArrangementRegistry` accepts one legacy value solely for compatibility.

## Invariants and constraints

- CPython 3.10, PySide6 6.4.2, and current public shortcuts remain fixed.
- Pinning never changes Files selection order or logical slot IDs.
- 2-, 4-, and 6-view tile geometry remains equal-sized after reordering.
- 3- and 5-view pinned documents occupy the existing enlarged first tile.
- Difference promotion and explicit user pinning retain their current priority
  rules.
- Split mode remains enabled when navigating from Bayer/RGB to GRAY; GRAY may
  legitimately display as one full-size viewer in the Multi View container.
- No unsplit source frame or obsolete grid placement may be painted during a
  Split Channels document transition.
- Docked maximize restores to the original dock area; floating maximize
  restores to its previous floating geometry.
- Hide/show does not silently re-dock or reset the selected Plots tab.
- Esc clears ROI only; Shift+Esc clears the shared line only.
- Persistence tests isolate QSettings and do not depend on test order.

## Proposed design

### P1-D

1. Treat the existing pin as a primary-order control for all Multi Views.
2. Expose it whenever the target displayed-document count is greater than one.
3. Keep `_multi_display_order` as display-order ownership and retain
   `_focus_document_id` as the pinned primary document while it remains valid.
4. Update tooltip and documentation terminology to describe first-tile pinning;
   explain that only odd focus layouts enlarge the first tile.
5. In `MultiCompareView.set_documents()`, compute and apply target geometry and
   viewer visibility before binding new documents.
6. Batch geometry and document replacement with widget updates disabled only
   for the critical section, then re-enable updates and issue one final update.
7. Preserve the existing loading-placeholder rule so an unsplit source image is
   never flashed while a split-capable document is pending.

### P1-E

1. Give floating Plots geometry an explicit QSettings key and a defined restore
   order relative to `restoreState()`.
2. Route title-bar double-click through the same maximize/restore state machine
   as the explicit button.
3. Rename the Edit action without changing callback or shortcut.
4. Characterize selected-tab persistence before changing dock restoration.

### P1-F

1. Characterize startup, reset, fixed geometry, and six-source restore first.
2. Remove compatibility registry and arrangement state in a dedicated change.
3. Ignore or delete legacy arrangement settings without exposing a new choice.

## Implementation slices

### P1-D slice 1 — Pin ordering for all Multi Views

- Files/components: `tile_header.py`, `multi_compare_view.py`,
  `main_window.py`, Multi View arrangement/toolbar tests
- Observable result: pin controls appear for 2–6 displayed documents; clicking
  one promotes it to the first tile without changing selection order
- Tests:
  - visibility for counts 1–6;
  - reorder behavior for 2, 4, and 6 views;
  - existing 3/5 focus geometry;
  - viewer identity/range preservation;
  - Difference plus source ordering;
  - tooltip and checked-state terminology

### P1-D slice 2 — Atomic Split Channels transitions

- Files/components: `main_window.py`, `multi_compare_view.py`, Split workspace
  tests
- Observable result: Bayer/RGB split views transition directly to one
  full-size GRAY viewer without an observable upper-left-grid intermediate
- Tests:
  - Bayer 4 -> GRAY 1;
  - RGB 3 -> GRAY 1;
  - GRAY 1 -> Bayer 4;
  - pending placeholder -> loaded channels;
  - at first non-null document binding, target geometry and visibility are
    already applied;
  - no duplicate fit/upload caused by the transition

### P1-E slice 1 — Persistence characterization

- Files/components: `main_window.py`, existing UI smoke/persistence tests
- Observable result: selected tab and current dock state have explicit
  regression coverage before changes
- Tests: fresh/saved/invalid settings and reset behavior

### P1-E slice 2 — Floating geometry and double-click

- Files/components: `main_window.py`, `plots_dock_title.py`
- Observable result: floating geometry and maximize/restore survive hide/show
  and restart
- Tests: floating, docked, maximized, restored, title double-click

### P1-E slice 3 — Shortcut and terminology cleanup

- Files/components: `main_window.py`, action tests, user guide
- Observable result: Edit menu says `Clear ROI`; Esc and Shift+Esc affect only
  their intended selections
- Tests: ROI-only, line-only, and simultaneous ROI/line states

### P1-F — Arrangement compatibility removal

- Files/components: `main_window.py`, `multi_compare_view.py`, layout/reset
  tests, durable docs
- Observable result: no arrangement menu/action/field/setting remains; fixed
  layouts and six-source Difference restore are unchanged
- Tests: one-to-six geometry, pinned ordering, legacy setting handling, reset,
  six-source restore

## Validation plan

- Targeted UI tests for pin visibility/order, Split transition atomicity, Plots
  persistence, title interactions, shortcuts, fixed layouts, and six-source
  Difference restoration.
- `scripts/check_docs.py` after every durable-document update.
- Full pytest, Ruff check, Ruff format check, mypy, and pip check for each phase.
- Manual Windows checks:
  - pin and reorder 2/3/4/5/6 views;
  - Bayer split -> GRAY and RGB split -> GRAY navigation at normal interaction
    speed;
  - floating geometry, double-click, hide/show, maximize/restore, restart, and
    reset.
- No packaging tools.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Pin semantics unexpectedly change Line Profile reference priority | reference-selection tests | explicitly define pinned primary as highest reference priority |
| Reordering even views changes selection or logical IDs | ordering tests | mutate only `_multi_display_order`, never `_selection_order` |
| Pre-layout content batching introduces blank or stale frames | transition-order and placeholder tests | apply target geometry first, disable updates only for the batch, then repaint once |
| Layout refit runs twice after split transition | fit/upload spies | retain one owner for refit completion and remove redundant calls |
| Qt saves stale floating geometry | restart tests and manual multi-monitor check | save only valid floating geometry and validate restore |
| Double-click conflicts with drag | focused event test and manual title-bar check | use existing toggle path and accept only left-button double-click |
| Removing arrangement state breaks restore | layout and six-source tests | perform P1-F only after P1-D/E characterization |
| QSettings tests become order-dependent | randomized/full-suite run | isolate organization/app names and clear settings per test |

## Phase dependencies and review boundaries

1. **P1-D first:** establishes the intended primary-order semantics and fixes the
   user-visible Split transition.
2. **P1-E second:** independent dock/persistence work with a narrower test
   matrix.
3. **P1-F last:** removes compatibility state after the preceding behavior is
   mechanically protected.

Each phase should be independently mergeable and should not carry deferred code
for a later phase.

## Progress log

- 2026-08-06: Audited PR #1–#9 excluding #7 and current `main`.
- 2026-08-06: Confirmed P1-B reference selection and selected-tab persistence
  are complete.
- 2026-08-06: Confirmed Esc behavior is correct but its label is stale.
- 2026-08-06: Confirmed arrangement storage is compatibility-only.
- 2026-08-06: Added even-view pin ordering requirement.
- 2026-08-06: Identified non-atomic document-before-layout ordering as the
  Bayer-to-GRAY Split transition flicker mechanism.
- 2026-08-06: Split the remaining workspace work into P1-D, P1-E, and P1-F.

## Completion summary

Fill in separately for each phase:

- Delivered behavior:
- Changed files:
- Validation results:
- Manual checks:
- Remaining limitations:
- Follow-up issues:
- Durable docs updated:
