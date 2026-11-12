# Memo reusable crops and simple editor

Status: Implemented; full native validation blocked by runtime conditions.
Owner: ChatGPT-assisted, 2026-11-12.
Continuation of open PR #229; no sleep or wake schedule is requested here.

Owner scope: exact crop-only exported PNGs with text only in HTML/metadata;
diagnose WinError5 on repeat saving; selecting ROI centers the resident Viewer;
remove Memo crop preview and redundant coordinate/source summary. Missing originals
provide no alternative in-app image; saved report assets remain externally usable.

Inspect native directory sharing locks and replace root-directory swapping with
guarded file publication if reproduced. Preserve earlier generation/recovery data
on failed writes and retain committed revision on cleanup warnings. Keep all owner
files, existing map/ZIP reads, numerical/Session/reset semantics and single Save.
Validate failure/rollback/locks, exact PNG dimensions/pixels, navigation without
reload, minimal UI and actual Windows rendering, then full local checks/review.

## Implementation checkpoint

- Reproduced old root rename failure with native Windows handles: open index.html
  without delete sharing gives WinError5; open directory gives WinError32.
- Stable-root backup/publication commits metadata last; unchanged PNGs are skipped.
  Derived HTML supports write-sharing handles. Genuine write locks remain errors.
- Exact recorded PNG bytes only in src/crops; no text, margins or duplicate originals.
- Removed Memo preview and coordinate summary; list selection centers resident
  viewers while preserving zoom, native arrays and generations. Missing sources
  provide no alternate in-app image.
- Actual Windows Qt capture: 10-simple-memo.png and 11-exact-crop.png, visually checked.
- Read-only independent review: no actionable findings; independent folder tests
  19 passed in 7.90s. Committed source: e8b772ff001bc6148bc3c534fc43fa9d2e65e1e9.
- Ruff src/tests passed; format 354 unchanged; mypy 134 source files passed;
  docs contract passed; strict MkDocs built successfully.
- Broad repository Ruff additionally reports four pre-existing findings in owner
  untracked diagnose_gc_pre569.py/diagnose_gc_survivors.py, left untouched.
- Attribution: owner-authenticated commit includes ChatGPT coauthor;
  PR #229 will remain open and ChatGPT-assisted. No merge or new sleep requested.

## Observed validation and remaining gate

- `.venv/Scripts/python -m pytest -q --tb=short` with the ten focused Memo/W09
  modules: **68 passed in 37.33s**.
- `.venv/Scripts/python -m pytest -q --tb=short
  --junitxml=temp/memo-simple-final-full-20261112.xml`: **1946 passed, 10 failed,
  1 warning in 508.45s**. Nine failures report Windows clipboard access denial;
  one RAW dialog initial-size test times out. The warning is the intentional
  duplicate ZIP member tamper fixture. No Memo regression failed.
- Exact failed-node rerun with native escalation, recorded in
  `temp/memo-simple-ten-recheck-20261112.xml`: **10 failed in 10.90s**;
  clipboard reports CLIPBRD_E_CANT_OPEN. Standalone native OpenClipboard also
  fails with error 5 and no reported clipboard-lock PID. Its cause is not fully
  established; no clipboard contents were read.
- Standalone RAW geometry: actual `(280, 749)`, sizeHint `(262, 899)`, screen
  available `(0, 0, 1024, 720)`. Current display cannot meet that test's equality
  condition. Do not weaken assertions, increase arbitrary timeouts or alter
  unrelated product code to hide either condition.
- `.venv/Scripts/python -m ruff check src tests`: exit 0.
- `.venv/Scripts/python -m ruff format --check src tests`: 354 files unchanged.
- `.venv/Scripts/python -m mypy src`: success, 134 source files.
- `.venv/Scripts/python scripts/check_docs.py`: Documentation contract passed.
- `.venv/Scripts/python -m mkdocs build --strict`: exit 0, site built.
- `git diff --check`: clean. Durable-document deletions inspected: narrow Memo
  contract corrections only; no unrelated contraction. Owner untracked files kept.

Changed implementation files: io/memo_folder.py, io/memo_report.py,
io/memo_archive.py, ui/review_panel.py, ui/review_window_integration.py,
ui/review_capture_adapter.py; removed ui/memo_report_images.py. Regression files:
test_memo_folder.py, test_memo_evidence.py, test_memo_report_images.py and
test_memo_roi_workflow.py. Product/architecture/decisions/current-state/user-guide
and visual-guide records were updated narrowly.

Manual/visual checks: actual Qt main/Memo capture and saved PNG were inspected;
PNG has no margin or text. Automated Windows handle tests cover open directory,
HTML and unchanged crop. Source-free viewing retains notes without a preview.
Exclusive file locks/ACL denial still require retry. Publication is metadata-last,
not crash-atomic; simultaneous readers can reject intermediate inventories.

Deferred: rerun the ten native failures and full local suite in an environment
with working clipboard access and adequate display space. No full-suite PASS,
merge-readiness, merge or new sleep is claimed.
