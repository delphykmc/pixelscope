# Execution plan: Issue #77 WP-C Quick Compare workflow

Status: Implementation complete / independent review pending
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
- Interactive additive page reveal is intentionally narrow: an exact one-source Files
  addition, Quick Compare additive input, and same-position folder bootstrap may
  reveal the Comparison Page containing the newly added source. Selected order and
  page size remain unchanged, while bulk/replacement/reconstruction workflows keep
  their established page semantics.
- Explicit Quick Compare Difference intent for:
  - sequential single-file A then B drop;
  - exactly two source files dropped together.
- No automatic pair choice for three or more dropped sources.
- Preservation of an existing valid Difference binding when more sources are added.
- Current Comparison Page ownership for Difference calculation; the dropped pair is never pinned across pages.
- Exactly-three-tile Equal/Focus geometry, implemented as a narrow override of the existing fixed geometry function.
- Context default:
  - ordinary three-source and split three-plane presentations -> Equal;
  - any three-tile presentation containing Difference -> Focus.
- Transient user override between Equal and Focus with no QSettings/session schema.
- Hold-B presentation-only blink for exactly two selected source documents in both Single View and Multi View.
- In Single View, the currently visible selected source is the Blink reference and the other selected source is the alternate, independent of selection order.
- Blink alternate presentation follows the current Display Gain mapping; release returns presentation ownership to the visible reference viewer and its current gain authority.
- B-key exclusion while text/numeric controls own focus; modifier-bearing B is not Blink.
- Preservation of folder-drop behavior over the Image View by delegating directory-containing drops back to the existing main-window drop owner.

## Out of scope

- Generic arrangement registry, arrangement menu, persisted layout variant, or session schema change.
- Automatic Difference for ordinary Ctrl-selection, Session restore, folder navigation, curation, or any generic `selected count == 2` state.
- Arbitrary Difference pair selection from 3+ dropped sources.
- Difference normalization/conversion outside the existing compatibility lifecycle.
- N-way Blink, Blink cycling, or logical source swapping.
- Changes to 4/5/6-view geometry or the established 5-view composition.
- Files-tree selection authority, Primary authority, ROI/Line numerical contracts, Remote IQA, packaging, or dependencies.

## Architecture

### Quick Compare input

`QuickCompareController` is installed last in `_compose_main_window_presentation()` so it observes the finalized registration, RAW/YUV, Difference, display-gain, workspace, and large-folder composition.

A QApplication event filter accepts local drops only when the target is within the central presentation stack. Pure file drops use the existing discovery/registration path, de-duplicate document IDs, and append new IDs through `_select_document_ids(..., preserve_view=True)`. Directory-containing drops are delegated to the pre-existing `_handle_dropped_paths()` path instead of creating a second folder workflow. DragEnter and DragMove are both accepted on these existing Image View surfaces so the native Windows cursor remains in an allowed-drop state throughout the gesture.

The controller never turns ordinary selection into a Difference command. It derives an explicit Difference pair only from the current drop gesture. Sequential single-file drops also keep one transient previous-drop anchor so already-registered/already-selected sources can still express explicit A-then-B Quick Compare intent without duplicating source state. Async source readiness is polled with a bounded timer before delegating the exact pair to the existing `DifferencePanel`; incompatible pairs keep their sources selected and expose the existing Difference status instead of hidden conversion.

A pending/in-flight Quick Compare pair is protected from retargeting until completion or invalidation.

For an explicit two-source Quick Compare pair that changes selection, PixelScope preserves the normal `_render_selection()` call so layout mode, capacity, action state, analysis ownership, and other internal presentation state advance exactly as they would without Quick Compare. To avoid exposing the transient two-source composition before Difference is ready, only repainting of `central_stack` is temporarily disabled. Difference calculation and preview publication proceed normally while the internal two-source presentation is already composed. When `result_ready` has allowed `MainWindow` to compose A/B/Difference, updates are re-enabled on the next event-loop turn so the user sees the final three-tile presentation at once. Incompatibility, timeout, selection invalidation, calculation failure, preview failure, or window close releases the repaint hold and exposes the already-valid source presentation. No render/state transition is skipped.

### Interactive additive page reveal

The Current Comparison Page remains derived from Selected and `_page_start`; there
is no second page model. Files-tree selection detects only an exact one-source pure
addition and, when that source would be off-page, advances through the existing
`_sync_comparison_page_to_index()` authority before rendering. Programmatic additive
workflows opt in explicitly with `reveal_document_id`; Quick Compare passes its final
new source and the same-position bootstrap passes the added source. Calls without
that opt-in, selection replacement/removal, and bulk Files selection retain their
existing page behavior.

### Three-view geometry

The controller wraps the already-composed `MultiCompareView._prepare_viewers_for_documents()` and `_fixed_geometry()` instance methods. Only `count == 3` can differ from the established geometry:

- Equal: three equal columns.
- Focus: the existing large-left + two-stacked-right geometry.

The presentation membership, including whether a Difference tile exists, selects the default. Manual override is transient for the current presentation context. Changing the presentation resets to its natural default. `capture_view_state()` / `restore_view_state()` preserve pan/zoom while a user switches variant.

Counts 1/2/4/5/6 delegate unchanged to the original geometry function. The `3 View` control is inserted before the existing trailing command-row stretch and the command-row metric owner is refreshed so the control participates in the composed presentation row rather than sitting outside its sizing contract.

### Blink Compare

Blink does not call `set_document()`, selection mutation, Primary mutation, Difference mutation, or any analysis API. It changes only the rendered presentation owned by the visible reference `ImageViewer`, then returns presentation ownership to that same viewer on release or application/window deactivation.

Eligibility is exactly two selected source documents, no channel-split presentation, and loaded previews. In Multi View, selected order provides deterministic reference/alternate ordering. In Single View, the currently visible selected source in `window.viewer` is authoritative as the reference and the other selected source becomes the alternate; this prevents Blink from targeting a hidden multiview tile when the second selected source is currently visible.

Blink preserves Display Gain semantics without performing memory-heavy full-frame rendering on the GUI thread. If an alternate viewer already owns a presentation at the current gain, or the controller's one-entry `(document/source/preview/generation/gain)` cache contains it, that presentation is reused immediately. Otherwise Blink creates a `TaskWorker` for the same RAW/ordinary display-transform renderer used by `ImageViewer` and submits it to the existing bounded Display Gain thread pool. Request serial plus document/source/preview/generation/gain identity reject stale completion. Release, selection rerender, gain change, or shutdown cancels or invalidates stale work.

A successful current request fills the one-entry Blink cache. Repeated B presses for the same document/generation/gain reuse the cached presentation instead of recomputing the full frame. While Blink is held, a Display Gain change invalidates the old Blink request/cache, prevents the reference viewer's gain worker from overwriting the alternate, and schedules/reuses the alternate at the new gain. Release restores the reference viewer's owned display preview and resumes `_ensure_display_preview()` for the current gain. The logical `viewer.document` never changes.

ROI, Line Profile, active/focus state, Difference binding, pan/zoom, headers, Selected order, and document identity therefore remain unchanged. Focus/application loss forcibly ends Blink so a missed B-key release cannot leave the alternate presentation stuck.

## Tests added

`tests/ui/test_issue77_wp_c_quick_compare.py` covers:

- sequential additive A -> B drop and explicit A/B Difference;
- exact two-file batch pairing;
- 3-file batch with no automatic Difference;
- ordinary two-source selection remaining passive;
- Image View target guard versus Files panel;
- ordinary 3-source Equal default and manual Focus switch without authority mutation;
- A/B/Difference Focus default;
- unchanged 4/5/6 fixed geometry;
- presentation-only blink and restoration;
- numeric-input B-key guard and 3-source Blink no-op.

`tests/ui/test_issue77_wp_c_review_regressions.py` covers independent-review boundaries:

- Display Gain changes while Blink is held and release rejoins viewer presentation authority;
- application deactivation restores Blink without waiting for B-key release;
- Single View uses the currently visible selected source as Blink reference even when it is second in Selected order;
- Single View alternate presentation uses the current Display Gain rather than a hidden tile's released native preview;
- Quick Compare two-file intent crossing the six-item page boundary does not pin or retarget Difference;
- an existing Difference binding survives selection growth/pagination;
- the transient 3 View control remains inside the compact command row before its trailing stretch.

`tests/ui/test_issue77_wp_c_blink_runtime.py` covers the remaining runtime blocker from independent review:

- Single View Display Gain Blink schedules the full-frame alternate render on the bounded worker pool instead of the GUI thread;
- completion updates the held alternate only after the worker result is available;
- the completed presentation is cached and reused by a repeated B press at the same document/source/preview/generation/gain identity.

`tests/ui/test_issue77_wp_c_owner_followups.py` covers owner-observed workflow boundaries:

- Image View DragMove keeps the proposed copy/drop action accepted;
- an explicit two-source pair freezes only repaint while the internal two-source Multi View state still advances;
- successful Difference publication releases the repaint hold with A/B/Difference already composed as three tiles and Difference action active;
- incompatible Difference releases the repaint hold and leaves a valid two-source presentation;
- already-registered/already-selected sources still form an explicit sequential Quick Compare pair from A-then-B drop gestures.

`tests/ui/test_issue77_additive_page_reveal.py` covers the paging follow-up:

- an exact one-source Files addition crossing the six-source boundary reveals the
  page containing the new source;
- Quick Compare additive input uses the same reveal contract;
- bulk programmatic selection still starts on the first Comparison Page;
- multi-item Files selection is not converted into last-item page following.

Existing WP-A/WP-B tests remain the regression baseline for shared ROI and folder bootstrap composition.

## Validation plan for independent review

The independent reviewer should run at minimum:

```text
pytest tests/ui/test_issue77_wp_c_quick_compare.py tests/ui/test_issue77_wp_c_review_regressions.py tests/ui/test_issue77_wp_c_blink_runtime.py tests/ui/test_issue77_wp_c_owner_followups.py -q
pytest tests/ui/test_issue77_wp_a_roi_usability.py tests/ui/test_issue77_wp_b_folder_bootstrap.py -q
ruff check src/pixelscope/ui/quick_compare.py src/pixelscope/app/application.py tests/ui/test_issue77_wp_c_quick_compare.py tests/ui/test_issue77_wp_c_review_regressions.py tests/ui/test_issue77_wp_c_blink_runtime.py tests/ui/test_issue77_wp_c_owner_followups.py
ruff format --check src/pixelscope/ui/quick_compare.py src/pixelscope/app/application.py tests/ui/test_issue77_wp_c_quick_compare.py tests/ui/test_issue77_wp_c_review_regressions.py tests/ui/test_issue77_wp_c_blink_runtime.py tests/ui/test_issue77_wp_c_owner_followups.py
mypy src
python scripts/check_docs.py
pip check
git diff --check main...HEAD
pytest -q
```

Repository-wide Ruff baseline debt documented during WP-B is not part of WP-C unless a changed WP-C file introduces a new finding.

Manual review should additionally verify actual Windows drag/drop from Explorer while PixelScope and Explorer run at compatible, non-elevated integrity levels, sequential A then B showing A until A/B/Difference is ready, two-file batch drop avoiding a visible intermediate 2-view, already-registered A then B still triggering explicit Quick Compare Difference, 3 View Equal/Focus controls at production widths, hold/release B in both Single View and Multi View with stable zoom/pan, Display Gain parity during Blink, and no Blink activation while editing ROI or other text/numeric controls.

## Progress log

- 2026-09-11: WP-A PR #78 and WP-B PR #79 were merged; latest baseline became `main@36f672b6f63943c292ff2ef788f3a1b4ff899031` with no open PRs.
- 2026-09-11: Created `codex/issue-77-wp-c` from that exact main.
- 2026-09-11: Inspected main-window D&D/selection/Difference composition, `MultiCompareView` fixed geometry and reorder wrapper, and `ImageViewer` rendered-image/view-state ownership.
- 2026-09-11: Implemented additive Image View Quick Compare, explicit two-source Difference intent, transient 3-view Equal/Focus variants, and presentation-only Blink.
- 2026-09-11: Hardened modified-key/text-focus Blink ownership, in-flight Difference retarget protection, and directory-drop delegation.
- 2026-09-11: Added focused WP-C UI contract tests and opened draft PR #80 for independent review preparation.
- 2026-09-12: Independent review identified and then verified the async Display Gain restoration fix, focus-loss recovery, pagination coverage, and command-row integration.
- 2026-09-12: Follow-up review identified Single View visible-reference ownership and hidden-alternate Display Gain parity as blockers; implementation and regressions were updated.
- 2026-09-12: Further independent review found that the Single View gain fallback performed full-frame rendering synchronously on the GUI thread. Blink rendering was moved to the existing bounded Display Gain worker pool with request identity, cancellation, and one-entry reuse cache.
- 2026-09-12: A subsequent manual observation reported native Explorer D&D as prohibited and triggered several speculative D&D lifecycle/ownership changes. Re-testing older previously-known-good revisions showed the same symptom; the development process was running elevated while Explorer was not. The symptom was therefore traced to the Windows integrity/UIPI boundary rather than a WP-C code regression. The speculative D&D-specific changes and tests were reverted; this correction is retained in the record to avoid repeating the diagnosis.
- 2026-09-12: Owner follow-up under a normal non-elevated run found a DragMove cursor-feedback gap, an undesirable visible 2-view transition before automatic Difference, and no-op behavior for already-registered Quick Compare drops. DragMove acceptance and transient sequential-drop intent were added. The first attempt to hide the intermediate 2-view skipped `_render_selection()` entirely and therefore also suppressed required internal layout/action state, reproducing as A remaining visible until a third drop exposed A/B/C/Diff. The implementation was corrected to keep the full render/state transition and defer only `central_stack` repaint until Difference publication or failure.
- 2026-09-12: Owner paging follow-up narrowed page-follow behavior to interactive
  additive selection only: Files single-add, Quick Compare, and same-position bootstrap.
  Bulk/replacement/restore/curation page semantics remain unchanged.

## Completion summary

PR #80 remains intentionally Draft and unmerged. The retained implementation consists of the WP-C feature controller/composition plus independent-review Blink fixes and the owner-observed Quick Compare polish. The D&D architecture is not broadened in response to the elevated-process observation.

No numerical analysis semantics, generic layout registry, session schema, Files authority, packaging, or dependency change is included.

Automated/runtime validation remains an exact-HEAD merge gate; this record does not claim unexecuted checks as passing.
