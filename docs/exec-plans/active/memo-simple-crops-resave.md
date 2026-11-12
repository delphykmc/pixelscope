# Memo reusable crops and simple editor

Status: Active. Owner: ChatGPT-assisted, 2026-11-12.
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
  19 passed in 7.90s. Full local validation remains pending.
- Ruff src/tests passed; format 354 unchanged; mypy 134 source files passed;
  docs contract passed; strict MkDocs built successfully.
- Broad repository Ruff additionally reports four pre-existing findings in owner
  untracked diagnose_gc_pre569.py/diagnose_gc_survivors.py, left untouched.
- Attribution: forthcoming owner-authenticated commit includes ChatGPT coauthor;
  PR #229 will remain open and ChatGPT-assisted. No merge or new sleep requested.
