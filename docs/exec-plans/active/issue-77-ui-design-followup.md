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
- The ROI editor must follow the Issue #81 Qt lifetime discipline: no unbounded retained widgets and no new blocking nested event loop.
- The new three-view affordance must use the established PixelScope toolbar icon language rather than a second rendering style.
- PR #68 remains the authority for adaptive Image View command-row sizing and stretch allocation. This follow-up must not replace that policy with a new width-allocation scheme.
- Additional owner requests received during this PR must be added to the PR body/checklist before implementation.

## Work item A — compact ROI presentation and editor

Problem: WP-A placed X/Y/W/H plus Apply/Clear directly in the Statistics sidebar, consuming excessive width/height for a low-frequency exact-edit operation. The first follow-up version then used a verbose read-only `x/y/width/height` sentence that still looked custom rather than like a polished engineering tool.

Revised design after owner review:

- restore the compact two-row Region presentation (`Scope`, `Bounds`);
- represent geometry as compact position + size notation: `(x, y) · width × height`;
- keep `Bounds` and the geometry summary together on the left;
- align only the `Edit` command to the right;
- use `Edit`, not `Edit...`, with a smaller width reservation;
- use compact X/Y/W/H controls in the editor as a 2×2 field grid rather than a tall form;
- size the editor from its contents rather than a broad default button-box reservation;
- mutate shared ROI only when Apply succeeds;
- keep the dialog open with local validation feedback when the proposed ROI does not fit every current comparison frame;
- retain existing Esc/Clear ROI behavior outside the dialog.

Acceptance:

- [x] inline four-field production editor removed from the sidebar presentation;
- [x] compact `(x, y) · width × height` summary;
- [x] `Bounds` + summary left, compact `Edit` right;
- [x] compact editor geometry with no unnecessary width/height;
- [x] Apply reuses `_numeric_roi_requested()` / `_apply_shared_roi()`;
- [x] invalid proposal does not replace the existing ROI and does not close the dialog;
- [ ] focused owner Windows visual validation.

## Work item B — ROI editor lifecycle

Independent review at `a4eca2d186c18a0365a962d2500208354f154286` found one merge blocker: the production editor used `QDialog.exec()` and every completed Edit session remained parented under MainWindow until final window destruction.

Correction:

- keep at most one active ROI editor reference;
- use window-modal `QDialog.open()` rather than `exec()`;
- repeated Edit while the dialog is open raises/activates the same instance;
- on `finished`, clear the controller reference and schedule GUI-thread `deleteLater()`;
- add DeferredDelete regressions proving repeated Accept/Cancel does not accumulate dialog trees.

Acceptance:

- [x] no `QDialog.exec()` in the production ROI editor path;
- [x] only one active ROI editor instance;
- [x] duplicate Edit raises the existing instance;
- [x] deterministic disposal after Accept/Cancel;
- [x] lifecycle regression coverage;
- [ ] exact-head runtime validation.

## Work item C — compact three-view arrangement control

Problem: WP-C's separate `3 View | Equal | Focus` text group is spatially detached from the Layout selector and consumes too much command-row space for a two-state presentation choice.

Revised design after owner review:

- place one icon-only arrangement button immediately beside the existing Layout selector;
- button is not an on/off toggle; it cycles `Equal <-> Focus`;
- icon reflects the current geometry;
- render Equal/Focus with the shared high-DPI toolbar icon pipeline and the same 1.5 logical-pixel rounded stroke language;
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
- [x] icon follows existing toolbar stroke/high-DPI conventions;
- [ ] focused owner Windows visual validation.

## Work item D — preserve PR #68 Image View command-row allocation

Owner visual feedback after an intermediate follow-up showed Page and Picked becoming compressed/overlapping. Root cause was a follow-up override that set every non-spacer top-level stretch to zero. That contradicted the adaptive allocation deliberately established in PR #68.

Restored contract:

- PR #68 remains the command-row sizing authority;
- preserve the established top-level stretch weights rather than replacing them:
  - Layout group: `1`;
  - Comparison Page group: `4`;
  - Gain group: `1`;
  - Picked count: `1`;
  - Clear: `1`;
  - Keep: `1`;
  - trailing spacer: `1`;
- preserve `Page` and `Picked` as shrinkable/eliding metadata surfaces with their existing `Ignored` policies;
- preserve content-derived actionable floors for Layout/Gain/Clear/Keep and their font/style refresh behavior;
- the new three-view button lives inside the existing Layout group, so its only sizing effect is to increase that group's content-derived minimum;
- after adding the three-view child, refresh the existing `_CommandRowMetricRefresh`; do not introduce another top-level stretch owner.

Acceptance:

- [x] follow-up zero-stretch override removed;
- [x] PR #68 adaptive stretch weights preserved exactly;
- [x] new three-view button remains inside the existing Layout group;
- [x] existing metric owner is refreshed after insertion;
- [x] focused regression asserts the PR #68 stretch contract remains intact;
- [ ] rerun existing PR #68 constrained/FHD overlap regressions on exact HEAD;
- [ ] owner Windows visual validation of Page/Picked observability.

## Validation plan

Focused automated coverage:

- existing Issue #77 WP-A ROI semantics;
- existing Issue #77 WP-C Quick Compare / three-view semantics;
- compact production ROI summary/alignment;
- modal ROI confirm/reject behavior;
- non-blocking single-dialog lifetime + DeferredDelete cleanup;
- Layout-adjacent three-view control and 3-only enablement;
- 3-view Equal/Focus geometry and icon transition;
- exact preservation of PR #68 command-row stretch allocation;
- existing PR #68 Beta UI / DPI command-row overlap, content-floor, 1280×720, and 1920×1080 regressions.

Before merge, run the repository's normal exact-head validation gates including full pytest, Ruff check/format, mypy, docs check, pip check, and `git diff --check`, plus owner Windows UI validation.
