# Execution plan: Issue #77 WP-A ROI usability

Status: Complete  
Owner: Codex WP-A implementer  
Branch/PR: `codex/issue-77-wp-a` / not created  
Last updated: 2026-09-11

## Goal

Add a compact X/Y/W/H editor to Statistics `1. Region` and make numeric edits and
viewer drag gestures update the existing shared ROI authority in both directions.
Across selection, Comparison Page, folder-position, source-load, and Session-related
context changes, preserve the ROI only while its exact reference-space rectangle fits
every relevant ready frame; otherwise clear it instead of clipping it.

## Scope

### In scope

- Statistics ROI X/Y/W/H, Apply/Enter, and Clear controls.
- One bidirectional `MainWindow._shared_roi` authority for editor, overlays,
  Statistics/Histogram, and Difference ROI consumers.
- Exact all-reference-frame fit validation across selection and image-context changes.
- Focused RGB, Gray, Bayer, YUV, Difference, reference/sample-space, navigation, and
  Session regressions.
- Narrow product, architecture, decision, current-state, roadmap, and user-guide
  updates required by the delivered behavior.

### Out of scope

- Issue #77 WP-B folder comparison bootstrap.
- Issue #77 WP-C Quick Compare, three-view geometry, and Blink Compare.
- Named/multiple/saved ROI management or a new ROI persistence schema.
- Per-image effective ROIs, silent clipping, numerical resampling, or Qt-side image
  processing.
- Floating workspace z-order or dock-window architecture.

## Current state

- `ComparisonAnalysisPanel` displays read-only bounds in `roi_label`; it has no exact
  numeric editor.
- `MainWindow._shared_roi_changed()` clips a viewer proposal to the smallest native
  source shape and `_normalize_shared_roi()` clips again after context changes.
- `_selection_changed()` and `_select_document_ids()` normally clear the ROI before
  rendering, while folder-position navigation opts into overlay preservation.
- Issue #75 introduced `ImageDocument.reference_shape`; viewer ROI gestures already
  use that reference extent, but MainWindow normalization still uses native `shape`.
- Session v1 persists one shared `RoiBounds` and restores it through
  `_shared_roi_changed()` after the reconstructed page settles.

## Invariants and constraints

- `MainWindow._shared_roi` remains the sole shared ROI authority.
- ROI coordinates are non-negative, integer, half-open reference/full-resolution
  coordinates with positive width/height.
- Every relevant Current Comparison Page frame must accept the identical rectangle;
  no clamping or per-frame ROI is permitted.
- Existing Esc Clear ROI, Shift+Esc Clear Line, Difference, Session v1, dtype/channel,
  YUV chroma-footprint, Bayer lattice, worker, and Current Comparison Page contracts
  remain unchanged.
- Numerical work stays in `core`; the new Qt controls only publish lightweight bounds.
- CPython 3.10 and the pinned repository environment remain authoritative.

## Proposed design

`ComparisonAnalysisPanel` exposes lightweight apply/clear signals and mirrors the
current shared ROI into four bounded integer controls. `MainWindow` connects those
signals to its existing `_shared_roi_changed()` and `clear_roi()` paths. A Qt-free ROI
fit predicate validates the exact half-open rectangle against each document's
`reference_shape`. New ROI proposals that cannot be shared are rejected and the UI is
resynchronized to the unchanged authority. Context transitions retain the authority
only if it fits all relevant ready page frames; an invalid retained ROI is cleared
before presentation and analysis binding. Explicit Session reconstruction clears old
transient ROI state before restoring saved intent.

## Implementation slices

1. **Exact ROI fit contract**
   - Files/components: `core/roi.py`, `app/main_window.py`, unit/UI tests.
   - Observable result: context changes preserve exact valid reference-space bounds or
     clear them without changing the rectangle.
   - Tests: bounds predicate, selection/page/folder context, mapped frames.
2. **Compact numeric editor**
   - Files/components: `ui/comparison_analysis_panel.py`, `app/main_window.py`, UI tests.
   - Observable result: drag mirrors X/Y/W/H; Apply/Enter updates overlays and all
     consumers; Clear and Esc remove the same authority.
   - Tests: signal/UI state, consumer identity, invalid proposal feedback.
3. **Session and durable contract integration**
   - Files/components: Session controllers/tests and narrow durable docs.
   - Observable result: a new Session does not inherit an old ROI, while a valid saved
     ROI restores through the same exact-fit path.
   - Tests: saved/no-saved ROI restoration plus existing navigation suites.

## Validation plan

- Targeted automated tests: new Issue #77 WP-A unit/UI files plus existing ROI,
  viewer, Statistics, Difference, YUV, folder-navigation, spatial-mapping, and Session
  focused nodes.
- Full checks from `docs/QUALITY.md`: docs checker, full pytest, Ruff check, Ruff
  format check, mypy `src`, pip check, and `git diff --check`.
- Manual Windows checks: numeric editor density/alignment, keyboard Apply/Clear/Esc,
  drag synchronization, mixed-size selection preserve/clear, and YUV/Bayer/Difference
  presentation. Offscreen results will be reported separately from owner-visible checks.
- Performance or memory checks: no new arrays, workers, or caches; deterministic UI
  tests confirm no parallel ROI state or numerical path.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Native shape is mistaken for reference extent | mapped YUV/Bayer/Difference tests | validate only `ImageDocument.reference_shape` |
| Invalid context briefly leaves a clipped overlay | UI context-transition assertions | validate before viewer/panel binding and clear all consumers |
| Session without ROI inherits pre-open transient state | Session regression | explicitly clear ROI at the restore commit boundary |
| Enter/edit focus conflicts with application shortcuts | real Qt key-event test | scope Return handling to the spin-box line edits; preserve Esc action |
| Selection behavior changes Line semantics | existing line/navigation tests | change ROI lifetime only; retain established line reset/preserve rules |

## Progress log

- 2026-09-10: Confirmed baseline `origin/main@5f95d6ebbd4bc33079ed3583a03ce02814110e0a`,
  no tracked local changes, and preserved all unrelated untracked owner files.
- 2026-09-10: Read Issue #77 (no comments), current contracts, source/call sites/tests,
  and history. Identified native-shape clipping plus unconditional selection clearing as
  the two implementation conflicts.
- 2026-09-11: Implemented strict reference-shape fit validation before consumer
  binding, shared numeric ROI entry, selection/page preservation, and explicit Session
  restore acceptance. Kept derived Split drag disabled while allowing numeric
  reference-space input.
- 2026-09-11: Focused WP-A and surrounding regression matrix passed 169 tests. Full
  pytest reached 1211 passed and one expected Windows symlink skip; its sole failure,
  the unrelated folder-display-tag header node, was reproduced with unmodified
  `origin/main` source. A transient Bayer hover failure exposed by an initial 3-row UI
  layout was repaired by retaining the Region group's established 2-row height.
- 2026-09-11: Offscreen 980x720 render inspection confirmed a compact single-row
  X/Y/W/H + Apply/Clear editor inside the established 88 px Region group. Generated
  inspection artifacts were removed afterward.

## Completion summary

- Delivered behavior: one exact reference-space ROI can be entered numerically or by
  drag, mirrors bidirectionally, and survives context changes only while every relevant
  Current Comparison Page frame fully contains it.
- Changed files: ROI core fit predicate; MainWindow authority/reconciliation; Statistics
  editor; canonical/legacy Session restore; focused unit/UI regressions; narrow product,
  architecture, decision, roadmap, quality, current-state, and user-guide contracts.
- Validation results: 169 focused tests passed; full pytest produced 1211 passed, one
  platform-privilege skip, and one baseline-reproduced unrelated failure. Changed-file
  Ruff, mypy, docs, pip, and diff checks are recorded in the PR evidence.
- Remaining limitations: owner-visible native Windows interaction was not available;
  layout was inspected from a real offscreen Qt render and keyboard/mouse behavior was
  exercised through production-composition Qt tests.
- Follow-up issues: WP-B and WP-C remain separately owned.
- Durable docs updated: `CURRENT_STATE.md`, `PRODUCT_SPEC.md`, `ARCHITECTURE.md`,
  `DECISIONS.md`, `ROADMAP.md`, `QUALITY.md`, and `USER_GUIDE.md`.
