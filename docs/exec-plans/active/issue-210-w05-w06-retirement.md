# Issue #210 — W05/W06 retirement and canonical workspace cleanup

Status: **Draft cleanup contract; not implementation acceptance** (2026-11-06).
Baseline MAIN: `98d2a603d879b7989d21207c7615e5b246d10a4b`.

## Product decision

**Do not** re-expose Compare/Analyze/Review through `View → Workspace Layout`.
The presets merely choose existing Dock/splitter arrangements and add a second
state/QSettings system without demonstrated task-efficiency or data-flow benefit.
This reverses the earlier menu relocation suggestion.

- W05: retire the exposed Original 2/4, A/B/Diff, Diff Focus preset *overlay*.
  Preserve native 2/4/6 source comparison, user-selected Difference A/B/channel,
  explicit Calculate/cache, Primary/Active/Picked, toolbar Fit/100%/Sync, W04
  physical viewport restoration, and the pre-W05 3 View Equal/Focus control.
- W06: retire Compare/Analyze/Review selector, per-preset QSettings snapshots,
  restore-epoch/timer/controller, and width-sensitive toolbar changes whose only
  purpose is to accommodate the retired selector. Preserve Qt native Dock
  saveState/restoreState, user resize/splitters, View > Show Plots/Dock Plots,
  Reset Workspace Layout, off-screen floating-dock correction and deterministic
  QObject teardown **under a single canonical layout owner**.
- Memo: no automatic Review workspace activation; View > Memo is a *dock
  visibility* action only. Memo feature changes belong to a separate PR.
- IQA: do not import, instantiate or reconfigure private SUB IQA features from
  Base. Generic QDockWidget hosts are allowed, including the Reference Lite
  right-side contribution.

## Code cleanup inventory

| Area | Required disposition |
|---|---|
| `core/comparison_presets.py` | Remove W05-only plan/pair/preset abstractions once all imports and tests migrated |
| `ui/quick_compare.py` | Retain QuickCompare drag/drop and 3 View logic; remove `ComparisonPresetController` and its signals/overlays |
| `ui/presentation_controls.py` | Remove the unused W05 selector factory and controls; preserve other presentation, page, accessiblity controls |
| `app/main_window.py` | Remove W05 `_comparison_plan` overlay/branches; retain existing Difference and page authority |
| `ui/preset_view_state.py` | Determine whether still referenced by any non-W05 caller before deletion; preserve W04 capture/restore |
| `ui/workspace_presets.py` | Retire controller and per-preset persistence; migrate usable offscreen helper to generic Dock layer |
| `ui/beta_workspace_hardening.py` | Remain generic Dock/chrome/shutdown owner without W06 preset controller |
| `ui/toolbar_cleanup.py` (W09b) | Remove temporary hide-only workaround rather than retaining invisible QWidgetActions; coordinate stacked PR |
| `tests/ui/test_w05_comparison_presets.py`, `test_w06_workspace_presets.py` | Replace preset-specific tests with canonical user task tests; do not merely delete behavioral coverage |
| `tests/unit/test_comparison_presets_contract.py` | Remove only after comparison planner retired; preserve equivalent Difference identity/cache regression |

## Replacement acceptance (release gate)

1. Production composition contains **no** hidden W05/W06 selector widget/action,
   no duplicate Open QAction, and no `View > Workspace Layout` action.
2. 2/4/6 source page and files Selected/Current Page/Primary/Active/Picks stay
   authoritative; changing Difference A/B does not silently Calculate.
3. Fit/100%/Sync and A/B→Difference→Sources preserve W04 geometry/zoom, including
   Sync Off and RAW/YUV channels.
4. Plots dock hide/show, float, maximize, redock, user splitter sizes, restart,
   Reset Workspace Layout, and partially offscreen title-region recovery pass.
5. Existing Session v1 and .pxreview V1 re-open; neither stores retired W05/W06
   state as a source identity authority.
6. Reference IQA contributed right Dock and Memo independently show/hide;
   no Base import of SUB IQA; no forced re-layout on Memo open/close.
7. Run focused + full normal-GC Windows PySide6 pytest on final source SHA;
   independent exact-head review before merge.

## Branch/PR sequencing

- **PR A**: W05/W06 retirement and regression replacement. This branch.
- **PR B**: Memo persistent multi-ROI, saved crops and offline HTML. Keep separate
  from this PR, based on W09b #222 once its foundation is accepted.
- W09b PR #222 currently hides the old controls in
  `ui/toolbar_cleanup.py`; remove the temporary hide-only path when PR A is
  integrated, or explicitly reconcile on rebase. Do not merge the conflicting
  policies as independent permanent implementations.

Owner must record actual native results; this draft makes **no PASS claim**.

Co-authored-by: ChatGPT <noreply@openai.com>
