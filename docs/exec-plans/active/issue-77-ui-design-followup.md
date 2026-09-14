# Issue #77 UI Design Follow-up

Status: Active

## Purpose

Refine the presentation of the merged Issue #77 WP-A/WP-B/WP-C work without changing their numerical or workflow authorities. This branch is intentionally kept open for additional owner UX feedback while the PR is in progress.

Baseline:

- `main@00b7dd77f320adee7a9d681902bb19d86480ea4c`
- WP-A / PR #78 merged
- WP-B / PR #79 merged
- WP-C / PR #80 merged
- no open PR at branch creation

## Governing constraints

- `MainWindow._shared_roi` remains the sole shared ROI authority.
- ROI coordinates remain reference/full-resolution coordinates.
- Invalid ROI proposals remain non-destructive and are never silently clamped per image.
- Three-view Equal/Focus remains a narrow presentation variant, not a new top-level layout mode or persistent arrangement registry.
- Existing Selected / Current Comparison Page / Primary / Difference / Split / Session contracts remain unchanged.
- Additional owner requests received during this PR must be added to the PR body/checklist before implementation.

## Work item A — compact ROI editing

Problem: WP-A placed X/Y/W/H plus Apply/Clear directly in the Statistics sidebar, consuming excessive width/height for a low-frequency exact-edit operation.

Design:

- restore the compact two-row Region presentation (`Scope`, `Bounds`);
- show current bounds inline;
- add one `Edit...` action;
- edit X/Y/Width/Height in a small modal dialog;
- mutate shared ROI only when Apply succeeds;
- keep the dialog open with local validation feedback when the proposed ROI does not fit every current comparison frame;
- retain existing Esc/Clear ROI behavior outside the dialog.

Acceptance:

- [x] inline four-field production editor removed from the sidebar presentation;
- [x] compact `Bounds ... Edit...` presentation added;
- [x] modal exact ROI editor added;
- [x] Apply reuses `_numeric_roi_requested()` / `_apply_shared_roi()`;
- [x] invalid proposal does not replace the existing ROI and does not close the dialog;
- [ ] focused owner Windows visual validation.

## Work item B — compact three-view arrangement control

Problem: WP-C's separate `3 View | Equal | Focus` text group is spatially detached from the Layout selector and consumes too much command-row space for a two-state presentation choice.

Design:

- place one icon-only arrangement button immediately beside the existing Layout selector;
- button is not an on/off toggle; it cycles `Equal <-> Focus`;
- icon reflects the current geometry;
- keep the button position stable for every view count;
- enable only when exactly three Multi View tiles are presented;
- 1/2/4/5/6-view presentation leaves the button disabled;
- retain context-aware defaults: ordinary/split three-view -> Equal, A/B/Difference -> Focus;
- retain transient per-context override and no QSettings/session arrangement persistence.

Acceptance:

- [x] old text controls removed from the visible command row;
- [x] compact icon control placed beside Layout;
- [x] Equal/Focus state remains owned by the existing Quick Compare controller;
- [x] non-three-view states disable the control rather than moving surrounding controls;
- [x] geometry icon and tooltip update with the active variant;
- [ ] focused owner Windows visual validation.

## Validation plan

Focused automated coverage:

- existing Issue #77 WP-A ROI semantics;
- existing Issue #77 WP-C Quick Compare / three-view semantics;
- new compact production ROI presentation;
- modal ROI confirm/reject behavior;
- Layout-adjacent three-view control and 3-only enablement;
- 3-view Equal/Focus geometry transition.

Before merge, run the repository's normal exact-head validation gates including full pytest, Ruff check/format, mypy, docs check, pip check, and `git diff --check`, plus owner Windows UI validation.
