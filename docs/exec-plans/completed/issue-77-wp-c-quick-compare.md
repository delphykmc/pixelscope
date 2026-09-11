# Execution plan: Issue #77 WP-C Quick Compare workflow

Status: Implementation complete / independent review pending
Owner: ChatGPT WP-C implementer
Branch/PR: `codex/issue-77-wp-c` / PR #80
Base: `main@36f672b6f63943c292ff2ef788f3a1b4ff899031`
Last updated: 2026-09-11

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
- Hold-B presentation-only blink for exactly two selected source documents.
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

A QApplication event filter accepts local drops only when the target is within the central presentation stack. Pure file drops use the existing discovery/registration path, de-duplicate document IDs, and append new IDs through `_select_document_ids(..., preserve_view=True)`. Directory-containing drops are delegated to the pre-existing `_handle_dropped_paths()` path instead of creating a second folder workflow.

The controller never turns ordinary selection into a Difference command. It derives an explicit Difference pair only from the current drop gesture. Async source readiness is polled with a bounded timer before delegating the exact pair to the existing `DifferencePanel`; incompatible pairs keep their sources selected and expose the existing Difference status instead of hidden conversion.

A pending/in-flight Quick Compare pair is protected from retargeting until completion or invalidation.

### Three-view geometry

The controller wraps the already-composed `MultiCompareView._prepare_viewers_for_documents()` and `_fixed_geometry()` instance methods. Only `count == 3` can differ from the established geometry:

- Equal: three equal columns.
- Focus: the existing large-left + two-stacked-right geometry.

The presentation membership, including whether a Difference tile exists, selects the default. Manual override is transient for the current presentation context. Changing the presentation resets to its natural default. `capture_view_state()` / `restore_view_state()` preserve pan/zoom while a user switches variant.

Counts 1/2/4/5/6 delegate unchanged to the original geometry function.

### Blink Compare

Blink does not call `set_document()`, selection mutation, Primary mutation, Difference mutation, or any analysis API. It snapshots the reference viewer's already-rendered `ImageItem` image/rect and temporarily presents the alternate source's already-rendered image/rect. Release restores the snapshot.

Eligibility is exactly two selected source documents, no channel-split presentation, and loaded previews. Selection order gives deterministic reference/alternate ordering. ROI, Line Profile, active/focus state, Difference binding, pan/zoom, headers, and document identity are therefore unchanged.

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

Existing WP-A/WP-B tests remain the regression baseline for shared ROI and folder bootstrap composition.

## Validation plan for independent review

The independent reviewer should run at minimum:

```text
pytest tests/ui/test_issue77_wp_c_quick_compare.py -q
pytest tests/ui/test_issue77_wp_a_roi_usability.py tests/ui/test_issue77_wp_b_folder_bootstrap.py -q
ruff check src/pixelscope/ui/quick_compare.py src/pixelscope/app/application.py tests/ui/test_issue77_wp_c_quick_compare.py
ruff format --check src/pixelscope/ui/quick_compare.py src/pixelscope/app/application.py tests/ui/test_issue77_wp_c_quick_compare.py
mypy src
python scripts/check_docs.py
pip check
git diff --check main...HEAD
pytest -q
```

Repository-wide Ruff baseline debt documented during WP-B is not part of WP-C unless a changed WP-C file introduces a new finding.

Manual review should additionally verify actual Windows drag/drop from Explorer, 3 View Equal/Focus controls at production widths, hold/release B with stable zoom/pan, and no Blink activation while editing ROI or other text/numeric controls.

## Progress log

- 2026-09-11: WP-A PR #78 and WP-B PR #79 were merged; latest baseline became `main@36f672b6f63943c292ff2ef788f3a1b4ff899031` with no open PRs.
- 2026-09-11: Created `codex/issue-77-wp-c` from that exact main.
- 2026-09-11: Inspected main-window D&D/selection/Difference composition, `MultiCompareView` fixed geometry and reorder wrapper, and `ImageViewer` rendered-image/view-state ownership.
- 2026-09-11: Implemented additive Image View Quick Compare, explicit two-source Difference intent, transient 3-view Equal/Focus variants, and presentation-only Blink.
- 2026-09-11: Hardened modified-key/text-focus Blink ownership, in-flight Difference retarget protection, and directory-drop delegation.
- 2026-09-11: Added focused WP-C UI contract tests and opened draft PR #80 for independent review preparation.

## Completion summary

Implementation is complete on PR #80 and intentionally not merged. The code introduces one feature-local controller plus one composition hook and one focused UI test module. No numerical processing, generic layout registry, session schema, Files authority, packaging, or dependency change is included.

Automated/runtime validation is deliberately left for the requested separate independent-review session; this record does not claim unexecuted checks as passing.
