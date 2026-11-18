# PR #186 Histogram validation and merge

Status: Validation complete

Owner: ChatGPT, under owner authorization

Branch/PR: `perf/histogram-first-paint-layout`, PR #186

Last updated: 2026-10-16

## Goal and scope

Fix the two owner-reported Windows failures, review the complete Histogram/Analysis
presentation diff, validate related contracts, then merge if clean. The owner
reported that basic manual behavior appeared correct and explicitly authorized
sleeping the PC after successful merge. No production numerical algorithm,
dependency, packaging tool, worker ownership or source identity change is intended
in this repair.

## Baseline and diagnosis

- Main base: `8c084fa069a0a4a9a4899a54623493b1eb71e1e8`.
- Original PR head: `5b3de34ffba3d76b0a7d74e59a69b0405abc4d5c`.
- Reproduced the two Separate/Overlay failures: **2 failed, 2 passed in 2.42s**
  for `tests/ui/test_histogram_first_paint.py`.
- The tests called QWidget-only `isHidden()` on a pyqtgraph axis (QGraphicsItem).
  Replaced those calls with `isVisibleTo(PlotItem)`, retaining the requirement that
  axes are enabled before the containing PlotWidget is shown. A local API probe
  observed True for a shown axis inside a hidden PlotWidget and False after
  explicitly hiding the axis.
- The owner's original five-file command then passed: **35 passed in 14.50s**.
- Expanded UI coverage found two failures in `test_beta_pass2_component_resize.py`:
  old hidden-context expectations and top-edge equality for controls whose fixed
  heights now differ. Updated these to assert the reserved empty context row,
  marked previous curves during requests, clear removing plots, and exact vertical
  center equality. Also reconciled two old hidden-activity assertions in
  `test_p1a_files_statistics_header.py` with the reserved rail and idle hidden bar.
- The three changed UI test modules passed: **17 passed in 6.36s**.

## Review

Inspected the complete PR diff, result invalidation/error/replacement/clear paths,
Separate/Overlay arrangement, activity geometry, hover-series invalidation,
Histogram export readiness, YUV analysis delegation, responsive layout and native
resource shutdown. The review is a direct agent review, not an independent agent
or human approval. No additional production-code blocker was identified.

Retained curves are explicitly previous results: `last_results` and hover series
are cleared during a new request; Histogram export additionally checks request
identity, worker/timer completion and current results. Genuine clear still removes
plots. Existing source/cache/worker/lifecycle ownership is unchanged. Added narrow
architecture and User Guide documentation for these visible semantics.

## Validation

Environment: Windows, pinned CPython 3.10.11 x64, NumPy 1.24.4, OpenCV 4.8.1,
PySide6 6.4.2, normal automatic GC. Run pytest outside the restricted filesystem
sandbox because it blocks test-only atomic saves and Git writes.

The first expanded command used a nonexistent `test_wp_c1_yuv_analysis.py` and
collected no tests. The corrected expanded selection reached **66 passed, 2 failed
in 35.54s**, exposing the obsolete layout assertions described above.

- Full `.venv/Scripts/python.exe -m pytest -q`: **1471 passed in 378.71s
  (0:06:18)**. No skip, xfail, timeout inflation, GC workaround or production
  change was added in this repair.
- Ruff check and format excluding only the pre-existing untracked owner
  `scripts/diagnose_gc_disabled.py`, `diagnose_gc_pre569.py`, and
  `diagnose_gc_survivors.py`: passed, **345 files already formatted**.
- `.venv/Scripts/python.exe -m mypy src`: **no issues in 108 source files**.
- `.venv/Scripts/python.exe -m pip check`: **No broken requirements found**.
- `.venv/Scripts/python.exe scripts/check_docs.py`: **Documentation contract passed**.
- `.venv/Scripts/python.exe -m mkdocs build --strict`: passed, **2.12 seconds**;
  only the upstream Material advisory and informational vendor README navigation
  message were printed.
- `git diff --check`: passed. Durable document edits are additive and narrow;
  no cumulative contract was removed or condensed.

## Completion and remaining limits

Validation and direct source review are complete with no remaining blocker.
Latest-head CI remains the final merge check. PR #186's review/body/timeline record
the committed head, hosted results and actual merge SHA. The owner authorized merge
once checks are clean, followed by the supported S3 sleep transition.

Repair files: `tests/ui/test_histogram_first_paint.py`,
`tests/ui/test_beta_pass2_component_resize.py`,
`tests/ui/test_p1a_files_statistics_header.py`. Documentation:
`docs/ARCHITECTURE.md`, `docs/user-guide/workflows/inspect-histogram.md`, and this
validation record. The existing production implementation in PR #186 is unchanged.

The owner's untracked installer/GC files remain untouched. Agent Git activity uses
configured owner identity with `Co-authored-by: ChatGPT <noreply@openai.com>`;
GitHub review/body/merge activity discloses ChatGPT assistance under `delphykmc`.
Existing human commits are not rewritten. The ignored `temp/pr186-sleep.ps1`
helper uses the .NET Suspend API with force/disable-wake flags both false and is
launched only after successful merge; it is not production architecture.

The owner supplied basic manual acceptance; this agent did not perform a new
human monitor/flicker judgment. Fixed axis gutters and legitimate pane-count
reflows remain intentional PR tradeoffs, not measured end-to-end performance
claims. Full pytest remains local, never added to hosted CI.
