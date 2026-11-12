# Memo switch, ROI fit and clean footer

Status: Implemented; inherited full native validation gate remains blocked.
Owner: ChatGPT-assisted. Date: 2026-11-12. PR #229.

## Scope and invariants

Use a native keyboard-accessible pill switch; disable recording without selected
ready originals. Delete selected ROI records in one batch, clear the old analysis
box, select the next remaining record; support Ctrl+A. Closing hides all Memo
boxes, clears active ROI and cancels recording, retaining note records. Replace
center-only navigation with canonical physical-zoom ROI fitting through Viewer and
MultiCompareView owners. Keep existing sync/source/generation/Session authorities.
Reuse existing statistics+histogram cache, flush pending canonical analysis on list
navigation and test that revisits never call numeric analysis again. No second cache
or saved-statistics injection. Footer contains only Open/Save; successful Save opens
HTML automatically; routine status strings remain diagnostic only. Genuine IO
failures remain visible as a warning dialog. Header Saved/Unsaved marker remains.
No dependencies, packaging, merge or sleep. Post purposes/results as PR comment.

## Validation

Cover switch keyboard/disabled states, multi-delete/repeated Delete, active ROI
clear, hide/reopen, automatic report opening/no inline status, cache hits/invalidation,
fit with Sync on/off, unchanged source identity and stale callbacks. Run applicable
Qt/analysis tests plus Ruff/format/mypy/docs. Prior full native gate remains blocked
by clipboard/display constraints; never report its older result as a new full PASS.

## Implementation and review

Implemented in ui/review_panel.py, ui/review_window_integration.py,
ui/image_viewer.py, ui/multi_compare_view.py and ui/comparison_analysis_panel.py.
Regression updates are in test_memo_roi_workflow.py, test_memo_report_images.py,
test_memo_evidence.py and test_w09b_named_findings_roundtrip.py. Product,
architecture, decisions, current-state, canonical workflow and visual guide were
updated narrowly. Owner untracked files are preserved.

The switch subclasses QCheckBox and retains Space/focus/accessibility behavior.
Routine last_status is diagnostic only, without a hidden status widget. Header
Saved/Unsaved remains; save/preflight/busy refusals use warning dialogs, while
successful publication calls QDesktopServices.openUrl for root HTML. External-app
dispatch is intercepted in tests; no test launches a real browser.

Independent review found two defects, both corrected: unequal tiles initially
lost the common Sync scale/center, and preflight save refusals became invisible
after footer removal. Sync now fits all tiles, chooses the minimum physical scale,
constrains a common center to all ROI-visible intervals and uses canonical range
propagation in one owner transaction. Tests include unequal Focus tiles and a tall
edge ROI. Preflight warnings preserve existing data without starting a worker or
opening HTML.

No new Memo cache was introduced: existing native Statistics+Histogram results
already share source-generation/ROI/bin/interpretation keys. List selection flushes
the pending canonical request and replays those results immediately. Tests replace
the numerical function with a failing stub on revisits, assert current/presented
tokens and cache-object identity, then change bin settings to require recalculation.
Pair deselection resets the Memo context; existing document cache lifecycle remains
owned by the document/residency layer.

Initial automated capture attempted work before the existing layout-refit fence
settled and was correctly refused. Tests now wait for layout, physical geometry and
initial analysis readiness instead of relaxing capture fences or timeouts.
Native restart expectations now assert requested ROI fit rather than old saved zoom;
source, line, layout, Sync and Difference restore checks remain intact.

Actual Windows screenshot 13-switch-clean-footer.png was visually inspected:
green pill/white thumb, ROI framed with context, no status/report-link footer.
The Open/Save footer and header marker remain. Physical owner/DPI/multimonitor,
SMB and packaging validation are not performed here.

## Observed validation

- `.venv/Scripts/python -m pytest -q --tb=short
  tests/ui/test_memo_roi_workflow.py tests/ui/test_memo_report_images.py
  tests/ui/test_memo_evidence.py tests/ui/test_memo_chrome.py
  tests/ui/test_w09b_production_wiring.py tests/ui/test_w09b_named_findings_roundtrip.py
  tests/unit/test_memo_folder.py tests/unit/test_w09b_review_guards.py
  --junitxml=temp/memo-switch-final-focused-20261112.xml`:
  **48 passed in 40.19s**.
- `.venv/Scripts/python -m pytest -q --tb=short
  tests/ui/test_p2f_analysis_request_dedup.py tests/ui/test_w02b_presented_analysis.py
  tests/ui/test_wp_c1_yuv_production_integration.py tests/ui/test_w01_physical_zoom.py
  tests/ui/test_w04_review_view_state.py tests/ui/test_multiview_arrangements.py
  tests/ui/test_p1b_histogram.py
  --junitxml=temp/memo-switch-analysis-fit-20261112.xml`:
  **104 passed in 21.67s**.
- `.venv/Scripts/python -m ruff check src tests`: exit 0.
- `.venv/Scripts/python -m pytest -q --tb=short temp/test_memo_feedback_capture.py`:
  **1 passed in 3.38s**; regenerated the actual Windows screenshot for final source.
- `.venv/Scripts/python -m ruff format --check src tests`: 354 unchanged.
- `.venv/Scripts/python -m mypy src`: success, 134 source files.
- `.venv/Scripts/python scripts/check_docs.py`: contract passed.
- `.venv/Scripts/python -m mkdocs build --strict`: exit 0.
- `git diff --check`: clean. Durable-doc deletion counts inspected; corrections
  replace only superseded Memo behavior, preserving unrelated baseline contracts.

Deferred: full local run in a native environment with working clipboard and adequate
display space. Older 1946-pass/10-fail evidence is not a result for this source;
there is no new full-suite PASS or merge approval. No merge or sleep performed.
Commits use owner authentication with ChatGPT coauthor; PR/comment updates are
marked ChatGPT-assisted. No existing human commit is rewritten.
