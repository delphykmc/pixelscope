# Execution plan: Issue #77 WP-B folder comparison bootstrap

Status: Complete
Owner: Codex WP-B implementer
Branch/PR: `codex/issue-77-wp-b` / PR #79
Last updated: 2026-09-11

## Goal

Reduce the initial cost of comparing matching positions across registered folders.
From a currently selected image, the Files context menu can add a same-ordinal image
from a chosen registered folder, while Alt+PageUp and Alt+PageDown add the nearest
eligible previous or next registered folder. The resulting distinct-folder selection
continues to use the existing PageUp/PageDown Folder Position workflow.

## Scope

### In scope

- Image-row **Compare same position with...** submenu over eligible registered folders.
- Application-wide Alt+PageUp / Alt+PageDown bootstrap shortcuts.
- Natural ordinal lookup, additive Selected membership, duplicate-folder skipping,
  six-source capacity, and safe unequal-length handling.
- Focused unit/UI integration coverage plus narrow product, architecture, quality,
  current-state, roadmap, and user-guide updates.

### Out of scope

- Making folder rows Selected or adding a persisted folder-group authority.
- Filename-based pairing, wrapping folder order, or fallback to a different ordinal.
- Automatic Difference creation, Quick Compare, Image View drag/drop changes, 3-view
  geometry variants, Blink Compare, or WP-A ROI behavior.
- Floating workspace, session schema, numerical processing, or packaging changes.

## Current state

- `core/folder_navigation.py::plan_folder_navigation()` atomically moves an existing
  one-to-six distinct-folder selection by one ordinal; it does not add folders.
- `MainWindow._folder_documents` stores each registered folder's natural document order,
  while its insertion order matches Files top-level registration order.
- `MainWindow._folder_navigation_selection()` derives Folder Position exclusively from
  Selected documents, and `_select_document_ids()` is the canonical mutation boundary.
- `FilesContextMenuController.build_menu_for_item()` owns the production Files image-row
  menu. Folder rows are deliberately non-selectable.
- Application-wide PageUp/PageDown shortcuts and Files/viewer forwarding already own
  Folder Position; the Alt variants are currently unused.

## Invariants and constraints

- Registered, Selected, Current Comparison Page, Presented, and Resident remain separate.
- Folder rows never become Selected authority; one image document is the anchor.
- Ordinal means index within the existing natural folder-document sequence.
- Existing Selected order is retained and the new target is appended exactly once.
- Bootstrap is available only for one-to-five Selected documents from distinct folders;
  six sources is a safe no-op so the resulting group remains Folder Position eligible.
- Already-selected folders and folders without the anchor ordinal are ineligible.
- Previous/next registered-folder search is non-wrapping and follows Files registration
  order; PageUp/PageDown retains its existing atomic movement semantics.
- No bootstrap path calculates, activates, or retargets Difference.
- CPython 3.10 and the existing Qt/UI thread boundary remain unchanged.

## Proposed design

Add a Qt-free `FolderComparisonBootstrapPlan` and planner beside the existing Folder
Position planner. It validates the selected distinct-folder group, resolves the anchor's
natural ordinal, and returns eligible unselected folder targets in supplied registered
order. An optional direction selects the nearest target strictly before or after the
anchor folder without wrapping.

`MainWindow` chooses the current shortcut anchor through its existing active/focus/current
selection ordering, delegates all ordinal decisions to the planner, and appends the target
through `_select_document_ids(..., preserve_view=True)`. The context menu uses the clicked
selected image as an explicit anchor and exposes only eligible targets. Empty, invalid,
capacity, and unequal-length cases retain state and use compact status feedback.

## Implementation slices

1. **Pure bootstrap planning**
   - Files/components: `core/folder_navigation.py`, planner unit tests.
   - Observable result: exact eligible targets and directional nearest target are derived
     without runtime mutation.
   - Tests: next/previous, selected-folder skip, short folders, no wrap, invalid groups,
     capacity, and determinism.
2. **Canonical selection and shortcut integration**
   - Files/components: `app/main_window.py`, focused UI tests.
   - Observable result: Alt+PageUp/Down appends one same-position document and plain
     PageUp/Down continues to move the full group.
   - Tests: focus surfaces, primary/active/Selected order, duplicate/capacity no-op,
     subsequent navigation, and no Difference creation.
3. **Files context action and durable workflow**
   - Files/components: `ui/workflow_polish.py`, UI tests, durable docs.
   - Observable result: a selected image row offers eligible registered folder targets;
     folder rows remain registration-only.
   - Tests: menu contents/action, duplicate folder-name labeling, unavailable state, and
     existing Files drag/drop/context-menu regressions.

## Validation plan

- Targeted automated tests: new planner and WP-B UI tests plus existing folder navigation,
  input/navigation, workflow-polish, capacity, preload/promotion, and D&D contracts.
- Full checks from `docs/QUALITY.md`: docs checker, full pytest, repository Ruff check,
  repository Ruff format check, mypy `src`, pip check, and exact base-to-HEAD diff check.
- Manual Windows checks: production-composed context submenu and Alt+PageUp/PageDown from
  Files, Image View, and Statistics focus; then plain PageDown on the bootstrapped group.
- Performance or memory checks: no new decode owner; tests assert only the new Current
  Comparison Page target enters normal foreground loading.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Alt shortcut conflicts with PageUp/PageDown forwarding | production-composition key tests | distinct application shortcuts; leave plain bindings unchanged |
| Target folder order differs from Files order | ordered planner/menu assertions | supply explicit `_folder_documents` registration order |
| Addition bypasses selection lifecycle | authority and load-call assertions | mutate only through `_select_document_ids()` |
| Short target folder silently chooses another image | unequal-length tests | omit that folder; no ordinal fallback |
| Existing/automatic Difference changes | Difference lifecycle assertions | never call Difference commands and preserve passive selection semantics |

## Progress log

- 2026-09-11: Confirmed latest `origin/main@5f95d6ebbd4bc33079ed3583a03ce02814110e0a`,
  Issue #77 has no comments, and the only open PR is independent WP-A PR #78.
- 2026-09-11: Created `codex/issue-77-wp-b` from exact `origin/main`; preserved all
  unrelated untracked owner files.
- 2026-09-11: Inspected Folder Position, Files context-menu, shortcut/focus, Selected/page,
  Difference, registration order, capacity, preload, D&D, and test-harness contracts.
- 2026-09-11: Added the pure same-ordinal planner, canonical additive selection,
  application-wide Alt shortcuts, modifier-safe viewer forwarding, eligible image-row
  submenu, and duplicate folder-name qualification. The existing planner was unchanged.
- 2026-09-11: Focused planner/UI/navigation/input/capacity/preload matrix passed 118
  tests. The latest unfiltered full suite passed 1224 tests with one Windows privilege
  skip and only the folder-display-tag failure already reproduced on exact base
  `origin/main@5f95d6e` during PR #78 validation.
- 2026-09-11: Changed-file Ruff and format, mypy for 134 source files, docs checker, pip
  check, and exact diff check passed. Repository-wide Ruff retained four unrelated
  import-order errors and 65 pre-existing format candidates.
- 2026-09-11: Offscreen production menu inspection showed an unclipped 533x124 parent
  menu and 159x40 target submenu with the expected targets. Real Qt Alt events worked
  from Files, Image View, and Statistics focus; plain PageDown/PageUp then moved the
  bootstrapped group. Generated screenshots were removed.

## Completion summary

- Delivered behavior: a selected image can add the exact same natural ordinal from an
  eligible registered folder through context choice or non-wrapping Alt+PageUp/Down;
  the resulting group uses unchanged plain Folder Position navigation.
- Changed files: one Qt-free folder planner, MainWindow selection/shortcut integration,
  modifier-safe Image Viewer forwarding, Files menu presentation, focused unit/UI tests,
  seven narrow durable contracts, and this execution plan.
- Validation results: 118 focused tests passed; full pytest produced 1224 passed, one
  platform-privilege skip, and one baseline-reproduced unrelated failure. Changed-file
  Ruff/format, mypy, docs, pip, and exact diff checks passed.
- Remaining limitations: owner-visible native Windows interaction was unavailable; real
  offscreen Qt production composition covered focus, shortcuts, menu layout, and follow-on
  Folder Position. Folder search intentionally does not wrap and omits short folders.
- Follow-up issues: Issue #77 WP-C remains separate.
- Durable docs updated: `CURRENT_STATE.md`, `PRODUCT_SPEC.md`, `ARCHITECTURE.md`,
  `DECISIONS.md`, `ROADMAP.md`, `QUALITY.md`, and `USER_GUIDE.md`.
