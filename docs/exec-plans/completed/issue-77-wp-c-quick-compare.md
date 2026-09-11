# Execution plan: Issue #77 WP-C Quick Compare workflow

Status: Implementation updated / native Windows validation and independent re-review pending
Owner: ChatGPT WP-C implementer
Branch/PR: `codex/issue-77-wp-c` / PR #80
Base: `main@36f672b6f63943c292ff2ef788f3a1b4ff899031`
Last updated: 2026-09-12

## Goal

Complete Issue #77 after WP-A and WP-B by reducing direct image-comparison setup cost while preserving the existing Selected, Current Comparison Page, Primary, Difference, ROI, Line Profile, and presentation authorities.

WP-C consists of three intentionally narrow interactions:

1. Image View drop becomes additive Quick Compare input.
2. Exactly three presented tiles gain transient Equal/Focus geometry variants.
3. Exactly two selected sources gain presentation-only hold-B Blink Compare.

Issue #77 remains the product source-of-truth for acceptance criteria.

## In scope

- Image View local-file drag/drop only; Files-panel drag/drop keeps its existing registration/list ownership.
- Additive registration/selection through existing `_register_inputs()` and `_select_document_ids()` authorities.
- Explicit Quick Compare Difference intent for sequential A then B and exactly-two-file batch drops.
- No automatic pair choice for three or more dropped sources.
- Preservation of an existing valid Difference binding when more sources are added.
- Current Comparison Page ownership for Difference calculation; the dropped pair is never pinned across pages.
- Exactly-three-tile Equal/Focus geometry with the existing five-view geometry unchanged.
- Hold-B presentation-only Blink for exactly two selected sources in Single View and Multi View.
- Existing Display Gain numerical/presentation semantics and bounded worker ownership.

## Out of scope

- Generic arrangement registry/menu/persisted arrangement state.
- Automatic Difference for ordinary Ctrl-selection, Session restore, folder navigation, or curation.
- Arbitrary Difference pair selection from 3+ dropped sources.
- Hidden Difference normalization/conversion.
- N-way Blink or logical source swapping.
- Files-tree selection authority, Primary authority, ROI/Line numerical contracts, Remote IQA, packaging, or dependency changes.

## Architecture

### Quick Compare input and native D&D ownership

The first WP-C implementation used a QApplication-global event filter plus `acceptDrops` on a growing set of presentation descendants. Owner Windows Explorer testing exposed a prohibited cursor and complete Image View D&D failure through multiple attempted fixes. The approach was therefore retired rather than hardened target-by-target.

The current architecture has one native presentation owner: `PresentationDropHost`. It wraps the existing `central_stack` without replacing that stack's identity or its Empty/Single/Multi state authority. The host alone has `acceptDrops=True`; the wrapped stack and all nested QWidget descendants, including pyqtgraph view/viewport widgets, have native drop acceptance disabled. This avoids depending on whichever child happens to sit under the Explorer cursor and avoids pyqtgraph `GraphicsView.dragEnterEvent()` consuming/ignoring the external drag.

`PresentationDropHost` explicitly owns `DragEnter`, `DragMove`, `DragLeave`, and `Drop`. Local Explorer paths prefer `CopyAction` when available. On `Drop`, the host emits the local paths and composition routes them to existing owners:

- pure files -> `QuickCompareController.handle_image_drop()` -> existing discovery/registration/additive selection/Difference lifecycle;
- any directory-containing drop -> existing `MainWindow._handle_dropped_paths()` folder-registration workflow;
- Files panel -> remains outside the host and retains `DocumentListWidget` Enter/Move/Drop ownership.

The controller is removed from QApplication's native D&D route after the host is installed. A small application filter forwards only Blink key/deactivation/close events to the controller, so the older D&D branch in the controller cannot participate in production native target routing.

`MainWindow` remains the legacy top-level fallback outside the presentation host. Because it historically has Enter/Drop ownership but no explicit Move handler, a narrow window event filter completes local-path `DragMove` acceptance without intercepting presentation-host or Files-tree ownership.

For diagnosis only, `PIXELSCOPE_DND_TRACE=1` installs a read-only QApplication event trace. It records the Qt object/parent chain, URL/local-path availability, actions, and pre-handler accepted state. If a prohibited Explorer cursor produces no trace at all, process elevation/UIPI or another pre-Qt platform boundary must be checked before any further widget changes.

Synthetic Qt D&D tests are deliberately described as handler/ownership tests only. They do not claim to reproduce Windows OLE target negotiation; real non-elevated Explorer D&D remains a mandatory merge gate.

### Quick Compare semantics

Pure file drops use existing discovery/registration, de-duplicate document IDs, and append through `_select_document_ids(..., preserve_view=True)`. The controller derives an automatic Difference pair only from the explicit Image View drop gesture. Ordinary two-source selection remains passive.

Sequential A then B or an exactly-two-file batch can schedule Difference. Three or more dropped sources never cause an arbitrary pair choice. A valid existing Difference binding is not retargeted when later sources are added. Difference compatibility, cache, source-readiness, and Current Comparison Page ownership remain delegated to the established Difference lifecycle.

### Three-view geometry

Only exactly three visible tiles gain a transient geometry variant:

- Equal: three equal columns.
- Focus: existing large-left + two-stacked-right geometry.

Ordinary three-source / split three-plane presentations default to Equal. Any three-tile presentation containing Difference defaults to Focus. Counts 1/2/4/5/6 delegate unchanged to the original geometry contract. The compact `3 View` control is inserted before the existing command-row trailing stretch and remains transient rather than persisted.

### Blink Compare

Blink never mutates Selected order, Primary, active logical analysis source, Difference binding, ROI, Line Profile, or layout authority. In Single View the currently visible selected source is the reference, independent of Selected order; in Multi View selected order provides deterministic reference/alternate ordering.

Display Gain fallback rendering is asynchronous. Missing current-gain alternate presentation is rendered by `TaskWorker` on the same bounded Display Gain thread pool used by `ImageViewer`, with request serial plus document/source/preview/generation/gain identity checks. A one-entry presentation cache prevents repeat full-frame recomputation for an unchanged identity. Gain changes cancel/invalidate stale Blink work and schedule the alternate at the new gain. Release restores viewer-owned reference presentation and resumes `_ensure_display_preview()`.

Application/window deactivation ends Blink so a missed B-key release cannot leave the alternate presentation stuck.

## Tests added

`tests/ui/test_issue77_wp_c_quick_compare.py` covers core drop semantics, passive ordinary selection, 3-view defaults/switching, unchanged 4/5/6 geometry, and basic Blink authority/no-op behavior.

`tests/ui/test_issue77_wp_c_review_regressions.py` covers Display Gain/Blink restoration, focus loss, Single View ownership/gain parity, pagination Difference boundaries, existing Difference binding, and compact command-row placement.

`tests/ui/test_issue77_wp_c_dnd_runtime.py` covers the corrected automated D&D contract:

- exactly one `PresentationDropHost` owns Empty/Single/Multi presentation D&D;
- the wrapped stack and nested QWidget/pyqtgraph descendants are not competing native drop targets;
- local Enter/Move/Drop are accepted through the same host in all three presentation states;
- Files panel remains outside the presentation host and keeps its own drop ownership;
- non-local MIME is ignored;
- Single View Blink gain fallback executes on the bounded worker pool and reuses cached output.

The removed EmptyWorkspace-child regression is intentionally not retained because child-specific native ownership is no longer the architecture.

## Validation plan

Focused automated gate:

```text
pytest tests/ui/test_issue77_wp_c_quick_compare.py tests/ui/test_issue77_wp_c_review_regressions.py tests/ui/test_issue77_wp_c_dnd_runtime.py -q
pytest tests/ui/test_issue77_wp_a_roi_usability.py tests/ui/test_issue77_wp_b_folder_bootstrap.py -q
ruff check src/pixelscope/ui/quick_compare.py src/pixelscope/ui/presentation_drop.py src/pixelscope/ui/dnd_trace.py src/pixelscope/app/application.py tests/ui/test_issue77_wp_c_quick_compare.py tests/ui/test_issue77_wp_c_review_regressions.py tests/ui/test_issue77_wp_c_dnd_runtime.py
ruff format --check src/pixelscope/ui/quick_compare.py src/pixelscope/ui/presentation_drop.py src/pixelscope/ui/dnd_trace.py src/pixelscope/app/application.py tests/ui/test_issue77_wp_c_quick_compare.py tests/ui/test_issue77_wp_c_review_regressions.py tests/ui/test_issue77_wp_c_dnd_runtime.py
mypy src
python scripts/check_docs.py
pip check
git diff --check main...HEAD
pytest -q
```

Native Windows manual merge gate, using a non-elevated PixelScope process and ordinary Explorer:

1. Empty workspace -> first image: cursor remains allowed/copy-capable while moving; drop succeeds.
2. Loaded Single View -> second image: cursor remains allowed; additive A+B Quick Compare occurs and explicit A/B Difference follows the WP-C contract.
3. Multi View -> another image: cursor remains allowed; source is added without retargeting established Difference.
4. Files panel -> existing registration/list D&D remains unchanged.
5. Directory over Image View -> existing folder-registration behavior remains intact.

If any Image View case still shows the prohibited cursor, rerun with `PIXELSCOPE_DND_TRACE=1`. No trace means inspect process elevation/UIPI first. Trace present means use the exact watched QObject/parent chain rather than adding speculative child drop targets.

FHD/narrow-width 3 View command-row layout and hold/release B with stable zoom/pan remain manual validation gates.

## Progress log

- 2026-09-11: WP-A PR #78 and WP-B PR #79 merged; WP-C branch created from `main@36f672b6f63943c292ff2ef788f3a1b4ff899031`.
- 2026-09-11: Implemented initial additive Quick Compare, explicit two-source Difference intent, transient Equal/Focus 3-view variants, and Blink.
- 2026-09-12: Independent review drove Display Gain race/focus-loss/pagination/command-row hardening.
- 2026-09-12: Follow-up review drove correct Single View Blink ownership and Display Gain parity.
- 2026-09-12: Further review identified synchronous full-frame Blink rendering; it was moved to the bounded Display Gain worker pool with identity/cancellation/cache semantics.
- 2026-09-12: Owner manual Windows testing exposed the major validation failure: native Explorer D&D to Image View showed a prohibited cursor and did not work despite helper-level tests.
- 2026-09-12: Adding missing `DragMove` acceptance did not fix native Explorer D&D. A subsequent EmptyWorkspace-child opt-in also represented fragmented target-by-target ownership rather than a durable architecture.
- 2026-09-12: Critical independent review classified the repeated D&D failure as a merge blocker/process-quality incident and recommended observability plus single-owner presentation D&D.
- 2026-09-12: Reworked native Image View D&D around one `PresentationDropHost`, removed per-child EmptyWorkspace ownership, isolated Blink filtering from D&D, completed the top-level Move fallback, added opt-in native routing trace, and rewrote automated D&D tests to state their actual handler/ownership scope.

## Completion summary

PR #80 remains Draft and unmerged. The implementation has been structurally reworked after the repeated native D&D failure, but it is not considered fixed or merge-ready until exact-HEAD automated validation and the full native Windows Explorer manual gate above pass, followed by a fresh independent re-review.

Automated synthetic event tests are not evidence of native Explorer integration by themselves.
