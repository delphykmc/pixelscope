# Issue #210 — Retire W05/W06 preset engines

Date: 2026-11-06. Base MAIN: `98d2a603d879b7989d21207c7615e5b246d10a4b`.

## Product decision

The W05 Original2/4/A-B-Diff/DiffFocus and W06 Compare/Analyze/Review
presets duplicated source presentation and QDockWidget/QSplitter operations.
Moving them from the toolbar to a View submenu does not add a new workflow,
reduce real user steps, or simplify the code. **Do not recreate a Workspace
Layout menu or leave invisible widget/controller instances.**

W05's runtime overlay, state and selection widgets are retired, while
the canonical 2/4/6 Source/Page/Primary, raw Difference pair/cache, T shortcut,
zoom/sync/ROI, and 3-view Equal/Focus survive.

W06's per-preset QSettings and owner are removed. Keep the established
MainWindow dock/splitter/QSettings persistence, Reset, Plots floating title/lifecycle,
and native titlebar recovery under the existing beta hardening controller.

## Scope and migration

The old W05 and W06 preset-only tests and implementations are deleted.
Retirement tests assert the absence of hidden owners and the preservation
of real user controls. Migration removes `ui/workspace_preset` and
`ui/workspace_layouts/v1` without touching `ui/main_splitter`,
`ui/sidebar_splitter` or native `ui/dock_state`.

The November 9 integration also removes the unused `select_preset_pair()`
compatibility seam. Memo already uses the canonical Difference selectors without
requesting Calculate. See [the combined integration plan](memo-evidence-cleanup.md).

## Explicit dependencies

The original #224 retirement PR was separate from Memo. November 9 integrates it
with W09b #222 on `codex/memo-evidence-cleanup-20261109`, resolves the MainWindow
shutdown conflict and revises tests to assert native controls instead of retired
W06 owners. Neither earlier Draft should be merged independently of this work.

## Mandatory validation before merge

Native Windows CPython 3.10/PySide6 focused W05/W06 retirement,
existing W04 viewer/zoom/sync, 2/4/6 Current Page, legacy Difference,
native ROI/Line, beta Plots docking/floating, QSettings restart/reset,
normal-GC close, and **full pytest** on exact code HEAD.
Also Ruff/mypy/docs and independent code review, physical DPI/monitor checks.
These are requirements, **not claimed completed test results**.

Co-authored-by: ChatGPT <noreply@openai.com>
