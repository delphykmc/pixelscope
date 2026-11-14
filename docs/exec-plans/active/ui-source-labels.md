# UI-02: preserve resolved source labels in analysis views

Status: Active. Owner: ChatGPT-assisted. Last updated: 2026-11-14.
Parent: https://github.com/delphykmc/pixelscope/issues/230
Item: https://github.com/delphykmc/pixelscope/issues/233
Branch: codex/ui-source-labels-20261113.
Base: UI-01 Draft PR #232, 3d8dc8feb75623265740e2dd14ec69a41cd2bdfb.

## Observable problem and scope

With long identical basenames and repeated capture directories, Files/Viewer
already show reference_run / capture / chart_...png. Statistics, Histogram and
Line Profile prepend capture again. Explicit [Reference] tags also receive the
unnecessary prefix. Three real Qt before captures reproduce both cases.

Preserve owner-resolved/custom display names. Only an otherwise bare basename
in a standalone analysis widget receives its existing immediate-parent fallback.
Use one Qt-free formatting helper; do not parse tags or introduce another alias
resolver. Keep registration, IDs, arrays, generations, selection/ROI, request and
cache identities, Difference and Line reference selection unchanged. No new
settings/presets/export controls, dependency changes, merge or sleep are included.
This separate stacked change preserves UI-01's draft and existing owner files.

## Implementation and tests

Source: core/source_presentation.py, ui/comparison_analysis_panel.py,
ui/line_profile_panel.py. Tests: unit/test_source_presentation.py and
ui/test_source_display_alias.py. Existing weak contains assertions were strengthened
to exact equality: RED 1 failed in 3.09s. Pure cases cover resolved/tagged/deep,
Unicode/custom/derived/no-parent names and legacy basename fallback.
Integration assertions cover real Statistics rows/Histogram titles and tag changes
without new numerical work, changed source memory/generation/request/cache or Line
reference selection. The resolver and source path never change.

Focused command:

```text
.venv/Scripts/python -m pytest -q --tb=short
 tests/unit/test_source_presentation.py tests/ui/test_source_display_alias.py
 tests/ui/test_plot_statistics_contracts.py tests/ui/test_w02b_presented_analysis.py
 tests/ui/test_p2f_analysis_request_dedup.py tests/ui/test_p1b_histogram.py
 tests/ui/test_wp_c1_yuv_production_integration.py tests/ui/test_ui_readability_roi_summary.py
 --junitxml=temp/ui02-focused-resume-20261114.xml
```

Prior observed result on the same uncommitted source: 67 passed in 19.89s.
The credit-limited turn stopped before documentation/source commit/after captures;
its changes were preserved and this command is rerun on resumption. New full pytest
is not run; #229's 1961-pass result and UI-01's 82 tests are not this change's full gate.
Independent read-only preliminary review found no source finding and independently
ran 19 pure source-presentation cases in 0.07s; exact committed-head review follows.

## Capture and delivery limits

Before source: 3d8dc8fe. Synthetic RGB, isolated QSettings, production Qt composition
and QWidget.grab. Desktop available1024x720/DPR1. Larger1400x880 widget renders are
not physical FHD/DPI evidence. OS mouse/keyboard/SMB/packaging/Enterprise acceptance
is not claimed. Canonical approved screenshots are not promoted. Initial temporary
capture-runner stdout decoding errors were corrected by UTF-8 execution and clean
recapture; those were not product failures. Temporary capture code stays ignored.

Update current-state/product/architecture/compare-many guide and a numbered visual
report narrowly. Verify each PNG/metadata hash and source SHA. Report observed
commands, scope, manual captures, limits and attribution in the draft PR. Owner Git
identity includes ChatGPT coauthor; GitHub activity is ChatGPT-assisted. Existing
human commits and 13 owner untracked entries remain untouched.

## 2026-11-14 resumption checkpoint

Focused command above: **67 passed in 22.44s**, exit0. Ruff source/tests exit0,
format355 unchanged, mypy134 success, docs contract passed. Source/test files were
unchanged from the pre-interruption implementation during this rerun.
