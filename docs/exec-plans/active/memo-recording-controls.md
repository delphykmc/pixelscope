# Memo explicit recording controls

Status: Implemented; inherited full native gate resolved on 2026-11-13.
See the [final merge-readiness record](memo-switch-fit-clean-footer.md#2026-11-13-merge-readiness-closeout).
Owner: ChatGPT-assisted. Date: 2026-11-12.
Branch/PR: codex/memo-folder-live-switch-20261112 / PR #229.

## Goal and scope

Make new-ROI recording explicit while allowing Memo to stay visible for reading.
Remove duplicate Add/Delete buttons; Delete works only in the focused ROI list.
Esc retains the existing analysis ROI clear behavior and cancels Memo pending
capture/statistics/restore, clears Memo selection and retains existing records.
Opening the dock enables recording of future gestures; hiding disables/cancels it.
Toggling on or reopening never captures a pre-existing ROI. Saved PNG/HTML/map,
Session, source matching, numerical algorithms and unrelated native failures are
out of scope. Post an attributable PR comment explaining changes and purpose.

## Design and validation

ReviewPanel owns a checkable Record ROI button and a list-only Delete QAction.
Coordinator gates automatic capture and cancels pending epochs explicitly. Main
window Esc/analysis Clear intent notifies Memo before existing ROI clearing; internal
restore clear_roi is unchanged, preventing self-cancellation during restores.
Tests cover on/off, retained notes, no recapture, Esc pending statistics/restore,
Delete focus, existing source/reset and save contracts. Run focused Qt/W09 tests,
Ruff/format/mypy and docs checks. Earlier full native gate remains blocked by
clipboard denial and the current 1024x720 desktop; do not claim full PASS.

## Observed results

- Combined focused command: `.venv/Scripts/python -m pytest -q --tb=short
  tests/unit/test_memo_folder.py tests/ui/test_memo_evidence.py
  tests/ui/test_memo_roi_workflow.py tests/ui/test_memo_report_images.py
  tests/ui/test_memo_chrome.py tests/ui/test_w09b_production_wiring.py
  tests/ui/test_w09b_named_findings_roundtrip.py tests/unit/test_w09b_review_guards.py
  tests/unit/test_memo_report.py tests/unit/test_memo_archive.py
  tests/ui/test_issue77_wp_a_roi_usability.py tests/ui/test_p1e_plots_workspace.py
  --junitxml=temp/memo-recording-focused-20261112.xml`:
  **88 passed in 45.52s**. Includes docked/floating Delete focus, real floating Esc
  key event, pending-statistics cancellation, note retention and ordinary ROI paths.
- `.venv/Scripts/python -m pytest -q --tb=short
  temp/test_memo_feedback_capture.py tests/ui/test_w09b_production_wiring.py
  tests/ui/test_w09b_named_findings_roundtrip.py tests/ui/test_memo_report_images.py`:
  **11 passed in 20.29s**. Actual Windows capture 12-recording-controls.png visually
  inspected: On toggle, no Add/Delete row, notes and Save remain visible.
- `.venv/Scripts/python -m ruff check src tests`: exit 0.
- `.venv/Scripts/python -m ruff format --check src tests`: 354 unchanged.
- `.venv/Scripts/python -m mypy src`: success, 134 source files.
- `.venv/Scripts/python scripts/check_docs.py`: contract passed.
- `.venv/Scripts/python -m mkdocs build --strict`: exit 0.
- `git diff --check`: clean. Narrow cumulative documentation additions/corrections;
  no broad deletions. Owner untracked files preserved.

An initial floating test tried capturing immediately during dock geometry changes;
the existing capture fence refused the unstable context. Setup now floats the dock
before image loading and waits for the existing source/geometry readiness contract;
no assertions or timeouts were relaxed. Both dock modes then passed.

Independent read-only source review found no actionable defect and identified one
stale Product Spec Add/Delete sentence, corrected in this change. Final exact-head
confirmation follows commit. The preceding full-suite result was 1946 pass/10 fail;
it is not a validation result for this new source. Native clipboard/display
constraints remain deferred as recorded in memo-simple-crops-resave.md; no new full
run or clean-suite/merge-readiness claim is made here.

Changed implementation: app/main_window.py, ui/review_panel.py and
ui/review_window_integration.py. Changed tests: test_memo_roi_workflow.py,
test_memo_chrome.py and test_memo_evidence.py. Updated product, architecture,
decisions, current-state, canonical workflow and visual guide with the new capture.
Owner-authenticated commits use `Co-authored-by: ChatGPT <noreply@openai.com>`;
the requested PR comment is marked ChatGPT-assisted. No merge or sleep is requested.
