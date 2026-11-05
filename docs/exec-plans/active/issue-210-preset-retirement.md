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

`select_preset_pair()` in the Difference lifecycle is temporarily retained
as a safe no-implicit-Calculate canonical pair-binding compatibility seam
for the unmerged W09b Memo work; it must be renamed/retired during W09b
integration, not treated as a revived W05 product mode.

## Explicit dependencies

**Separate Memo work** is not in this PR. W09b PR #222 currently touches
central UI and has tests referencing W06 preset owners. It must be rebased
and tested against this retirement branch before integration; do not merge
both PRs independently into Main and hope to resolve conflicts automatically.

## Mandatory validation before merge

Native Windows CPython 3.10/PySide6 focused W05/W06 retirement,
existing W04 viewer/zoom/sync, 2/4/6 Current Page, legacy Difference,
native ROI/Line, beta Plots docking/floating, QSettings restart/reset,
normal-GC close, and **full pytest** on exact code HEAD.
Also Ruff/mypy/docs and independent code review, physical DPI/monitor checks.
These are requirements, **not claimed completed test results**.

Co-authored-by: ChatGPT <noreply@openai.com>
