# Execution plan: Issue #180 performance integration and Primary follow-up

Status: Active

Owner: ChatGPT, under owner authorization

Branch/PR: `codex/issue-180-primary-style`; follow-up to merged #182, #183, #184

Last updated: 2026-10-16

## Goal and scope

Validate the reviewed stacked PRs on Windows, merge #182, #183, and #184 in that
order, then reduce measured redundant GUI work during resident-source Primary
changes. Preserve source/viewer association, Active/Primary/Pick independence,
ROI/Line, Display Gain, Difference cache identity, generation and numerical results.
Packaging, dependencies, Enterprise IQA, OS file-read tuning, and a new integer
conversion pipeline are outside this slice. Issue #180 remains open until its
remaining acceptance evidence is available.

## Baseline and inspection

- Merged baseline: `origin/main@d5bfcc0a9b03177e1f455e7a54562bc7f3d3bb09`.
- Reviewed heads: #182 `99362bfddf96404b12889cd494632fcb6982929f`,
  #183 `bedca25c9b93eb63c8836e2fa731c14d60f8c498`,
  #184 `6e0c54b9b7a8b397b1ee43037f85fbfb28f7587c`.
- Read `CURRENT_STATE.md`, documentation map, applicable harness/quality rules,
  architecture and product contracts, Issue #180 and its implementation updates.
  Inspected changed source/tests, registration/Quick Compare/Difference/cache
  callbacks, MainWindow Primary rendering, MultiCompareView, ImageViewer and
  ReviewSelectionController.
- Target environment: Windows, CPython 3.10.11 x64, NumPy 1.24.4, OpenCV 4.8.1,
  PySide6 6.4.2. No dependencies or packaging tools installed.

## Implementation slices

1. Run changed-contract tests and broad static/docs checks on the combined head;
   run full Windows pytest with normal automatic GC before merging.
2. Merge parents with preserved ancestry, retarget each child to `main`, and merge
   with expected-head protection. Record ChatGPT assistance and co-authorship.
3. Measure resident 4K Primary switches before editing. Optimize only the identified
   redundant styling work; use explicit widget methods and no new runtime method
   replacement or ownership graph. Add regressions for unchanged-state no-ops,
   actual Active/Pick transitions, and production-composed Primary switching.
4. Update relevant durable/user documentation, rerun applicable checks, and deliver
   a separate reviewable follow-up PR. Do not treat its new implementation as
   covered by the owner's existing reviews of #182–#184.

## Validation and evidence

- Changed-contract command: `.venv/Scripts/python.exe -m pytest -q` with
  `tests/ui/test_issue77_wp_c_quick_compare.py`,
  `test_issue77_wp_c_owner_followups.py`, `test_issue77_wp_c_review_regressions.py`,
  `test_difference_cache_panel.py`, `test_difference_cache_toolbar_lifecycle.py`,
  `test_difference_keep_calculate_lifecycle.py`,
  `test_large_folder_registration_composition.py`,
  `test_files_drag_selection_debounce.py`, and unit
  `test_cv2_histogram_fastpath.py`, `test_histogram_worker_cancellation.py`,
  `test_diff_and_statistics.py`, `test_roi.py`: **81 passed in 33.67s**.
- `python -m mypy src`: **Success: no issues found in 108 source files**.
- `python scripts/check_docs.py`: **Documentation contract passed**.
- `python -m pip check`: **No broken requirements found**.
- Ruff check/format, excluding only the three pre-existing untracked
  `scripts/diagnose_gc_*.py` forensic files: passed; **344 files already formatted**.
  Initial unexcluded check reported four lint findings and three formatting
  findings in those owner files; they were preserved without edits.
- `git diff --check`: passed. All three latest-head GitHub static checks and
  screenshot comparisons passed; focused Windows CI was policy-skipped.
- Initial sandboxed full pytest was interrupted after reproducible environment
  failures: temporary Git writes and atomic `os.replace` saves were denied.
  Git-history tests rerun outside the sandbox: **2 passed in 3.41s**.
  Unrestricted full Windows run: **1467 passed in 390.23s (0:06:30)**.
  Final merged source has no diff against the tested combined head.

## Observational measurements before follow-up

Synthetic native RGB8 histograms, two warm-ups then ten repetitions per size,
exact bin equality on every repetition, pinned Windows environment:

| Input | OpenCV p50 / p95 ms | prior three-channel NumPy bincount p50 / p95 ms |
|---|---:|---:|
| 1920 x 1080 | 2.91 / 3.08 | 25.71 / 30.29 |
| 3840 x 2160 | 11.53 / 11.91 | 101.56 / 108.63 |

These are numerical microbenchmarks while other validation was running, not app
end-to-end speedups. No elapsed-time correctness threshold is introduced.

Production-composed MainWindow, two synthetic resident RGB8 3840 x 2160 sources,
Windows offscreen Qt, analysis settled, four warm-up switches, twelve measured
Primary switches with cProfile: synchronous dispatch **p50 29.04 / p95 35.48 ms**.
Of 361 ms cumulative Primary handling, MultiCompareView consumed 296 ms;
`setStyleSheet` consumed 258 ms across 192 calls. `_activate_viewer` repeatedly
called `ImageViewer.set_active` for all six viewers even when state was unchanged;
review tile synchronization also reapplied unchanged styles on document signals.
Histogram trace for the initial two-source analysis: worker 101.85 ms, GUI render
47.93 ms. This probe measures dispatch and Qt processing, not display scanout or
manual perceived latency. Temporary profiling code stays under ignored `temp/`.

## Risks and remaining checks

- Dynamic Pick selectors need an actual repolish when their property changes;
  skipping unchanged styling must preserve this transition.
- Initial inactive cursor styling must still initialize, and actual Active changes
  must update cursor opacity and border together.
- Native lifecycle/GC tests and applicable Windows interaction tests remain gates.
- Manual cold/warm file-I/O and first-painted-frame matrices, human visual review,
  and any further histogram-widget/layout optimization remain separately scoped.

## Progress log

- 2026-10-15: Owner authorized testing, sequential merge of the already-reviewed
  stack, and subsequent optimization. Existing untracked owner diagnostics and
  installer inputs preserved. Measured the next GUI bottleneck before editing.
- 2026-10-16: Full Windows validation passed. Merged #182 at
  `5bc70cdfe713fca337e83e99e7cc79cf4b521ef3`, retargeted #183 to main and merged
  at `99e336d4e223604600ce073595c3b832cdf11386`, then retargeted #184 to main
  and merged at `c453789574be6a68d24736a3bd2ed01748168522`. Preserved parent
  ancestry and guarded each merge with the tested expected head SHA. All PR bodies
  record ChatGPT-assisted validation; merge commits carry the ChatGPT co-author
  trailer. GitHub operations used owner account `delphykmc`; existing commits were
  not rewritten.
- 2026-10-16: Added unchanged-state/style guards to `ImageViewer.set_active` and
  `ReviewSelectionController._sync_tile`. New tests verify initial inactive styling,
  real Active cursor/border changes, Pick-property repolishing, and ten Primary
  switches in production composition with 2/3/6 sources and visible cached
  Difference cases. They reject any new source upload/load/analysis dispatch and
  assert stable source arrays, preview arrays, generations, analysis identity and
  source-to-viewer association. The first new-test run had a test-only reference
  to nonexistent `window._analysis_pool`; corrected it to `analysis._pool`.

## Follow-up validation and measurements

Repeated baseline profiling after the full run, on the merged source with no
concurrent validation: synchronous Primary dispatch **p50 29.31 / p95 31.58 ms**.
After the two styling guards, the identical probe measured **p50 8.07 / p95 8.79 ms**.
Both use four warm-ups, twelve cProfile-instrumented switches, two resident
synthetic RGB8 3840 x 2160 documents and offscreen Qt. Cumulative native
`setStyleSheet` time across all widgets fell from **253 ms / 192 calls** to
**11 ms / 96 calls**; the production regression separately asserts **zero tile
stylesheet applications** for the unchanged-state Primary switches. Other header
widgets still style themselves. Qt processing/paint and real display scanout are
separate from the synchronous dispatch measurement; no end-to-end claim is made.

New regression module: **7 passed in 6.31s**. Broader applicable follow-up validation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/ui/test_primary_style_work.py `
  tests/ui/test_multiview_arrangements.py `
  tests/ui/test_multiview_gain_diff_stability.py `
  tests/ui/test_p1d_multiview_polish.py `
  tests/ui/test_p4a_review_selection.py `
  tests/ui/test_p4a_review_selection_review_fixes.py `
  tests/ui/test_p3c_display_gain.py `
  tests/ui/test_p3b_raw_display_gain.py `
  tests/ui/test_viewer_interaction_contracts.py `
  tests/ui/test_background_work_lifecycle.py `
  tests/ui/test_issue81_qt_lifecycle.py `
  tests/ui/test_issue121_qt_gc_lifecycle.py `
  tests/ui/test_issue77_wp_c_quick_compare.py `
  tests/ui/test_difference_cache_toolbar_lifecycle.py `
  tests/ui/test_difference_keep_calculate_lifecycle.py `
  tests/ui/test_files_drag_selection_debounce.py
```

Result: **116 passed in 50.27s**, unrestricted local Windows with normal automatic
GC. No new Qt ownership graph or teardown mechanism is introduced. The full
1,467-test PASS belongs to the merged stack; the new follow-up has applicable
validation, not a second full-suite claim.

Follow-up broad checks:

```powershell
.\.venv\Scripts\python.exe -m ruff check . --exclude scripts/diagnose_gc_disabled.py,scripts/diagnose_gc_pre569.py,scripts/diagnose_gc_survivors.py
.\.venv\Scripts\python.exe -m ruff format --check . --exclude scripts/diagnose_gc_disabled.py,scripts/diagnose_gc_pre569.py,scripts/diagnose_gc_survivors.py
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts/check_docs.py
.\.venv\Scripts\python.exe -m mkdocs build --strict
git diff --check
```

All passed: **345 files already formatted**, mypy **108 source files**, docs
contract passed, strict User Guide built in **1.22 seconds**. MkDocs printed its
upstream Material advisory and an informational unlisted vendor README; the strict
build exited successfully. Reviewed durable-doc additions and the small deletions;
no historical contract or cumulative baseline was removed.

## Delivery and remaining scope

Changed production files: `src/pixelscope/ui/image_viewer.py`,
`src/pixelscope/ui/review_selection.py`. New regression:
`tests/ui/test_primary_style_work.py`. Updated `CURRENT_STATE.md`,
`ARCHITECTURE.md`, `PRODUCT_SPEC.md`, User Guide comparison/Difference workflows,
and this plan to reconcile merged behavior and retain evidence.

No new human visual/manual acceptance was performed. The follow-up remains a
separate reviewable PR; the owner's completed reviews applied to #182–#184.
Issue #180 stays open for manual display/first-paint matrices and any subsequent
profile-backed work. Remaining observed candidates include Line Profile empty-plot
refresh and histogram GUI rendering; no speculative changes to them are included.
Temporary profiling probes remain ignored under `temp/` and are not committed.
The local commit uses configured owner identity with
`Co-authored-by: ChatGPT <noreply@openai.com>`; the PR body discloses ChatGPT
assistance. No existing human commit is rewritten.
