# PR #194 source cycling validation and repair

Status: Complete (implementation review and validation; linked PR owns merge state)

Owner: ChatGPT, requested by repository owner

Branch/PR: [PR #194](https://github.com/delphykmc/pixelscope/pull/194)
Last updated: 2026-10-20

## Goal and scope

Verify plain T promotes the last actual source on the current Comparison Page
in Single/Multi View, without changing Selected order or including Difference.
Repair observed regressions, obtain independent review, run Windows validation,
and merge only after checks pass. Retire hold-B Blink. D&D zoom/pan behavior,
packaging, IQA boundaries, and unrelated local diagnostic files are excluded.

## Current state and invariants

The starting remote head is `9c2f09f`. MainWindow owns page-local source order;
QuickCompareController no longer owns Blink previews. Existing stable composition
hooks retain document-affine Multi View widgets. Preserve source semantics,
analysis request identity, shared ROI/Line, display gain, and deterministic Qt
teardown under CPython 3.10. No human commits will be rewritten.

## Work and validation

1. Inspect source, call sites, product/architecture contracts and related tests.
2. Replace obsolete Blink runtime coverage with current source-cycle/gain coverage;
   fix any reproduced functional regressions with focused tests.
3. Independently review the final diff; run focused UI, full local pytest, Ruff,
   mypy, docs, pip and whitespace gates from `docs/QUALITY.md`.
4. Exercise the source-built Windows app with real keyboard focus and inspect
   Single/Multi, Difference, gain and return-to-original source order.
5. Record exact results, update PR evidence, merge, then request Windows sleep.

## Progress

- 2026-10-20: Fetched and fast-forwarded to remote head. Earlier local `c3f6bbb`
  passed the initial five-module focused command (62 tests); this does not establish
  final-head validation. Remote scope deliberately excludes D&D zoom/pan changes.
- Independent reviewer reproduced one obsolete Blink runtime test failure:
  `test_issue77_wp_c_blink_runtime.py` still calls removed controller APIs.
- Replaced that retired test with actual Difference-on, gain-2 rendered-byte,
  shared-ROI and Selected-order assertions in Single/Multi View. Added Files,
  editor, modified-key, autorepeat, one-source and split-mode regression coverage.
  The two source-cycle modules passed 14 tests in 11.11 seconds. The original
  five-module PR command on remote head passed 61 tests in 27.27 seconds.
- CPython 3.10.11 / PySide6 6.4.2: mypy passed (108 source files), pip check,
  docs check, strict MkDocs build and whitespace check passed. Repository Ruff
  found only pre-existing untracked `scripts/diagnose_gc_*.py` issues (4 lint,
  3 format). Ruff lint and format on tracked Python plus the new runtime test
  passed (352 files); unrelated diagnostics remain untouched.
- Actual Windows UI checks through computer-use passed: two T presses restore
  the original two-source order; with Diff enabled T promotes source B, not Diff;
  Single View T changes A/B while keeping Diff enabled and gain 2x visible;
  Files-focused three-source Multi View cycles B/A/C -> C/B/A -> A/C/B -> B/A/C;
  B leaves presentation unchanged. Native input used a synthetic RGB gradient
  app with production application/presentation composition and isolated settings.
- The sandbox full run recorded Git/clipboard/settings failures and Windows
  exception `0x8001010d` inside the Session save dialog at about 33%; it was
  stopped without claiming PASS. Git-history tests independently passed outside
  the sandbox (2 passed in 3.86 seconds). Full normal-GC validation was subsequently
  rerun with native Windows access; final evidence follows below. No timeout
  inflation, skip or GC workaround was added.

## Final validation evidence

The native-access full run used the same source/test content subsequently committed
as `8a4c77e`; remote `c94e10d` only changed a heading and the already-removed final
blank line. `d730fe9` fixes plan Markdown whitespace only. No product source was
changed during this verification pass.

| Command | Observed result |
|---|---|
| `.venv/Scripts/python.exe -u -m pytest -q` (native Windows access, normal GC) | **1567 passed in 543.78s**, exit 0; zero skipped/xfail reported |
| `.venv/Scripts/python.exe -m pytest tests/ui/test_source_primary_cycle.py tests/ui/test_source_primary_cycle_runtime.py -q` | **14 passed in 11.11s** |
| `.venv/Scripts/python.exe -m pytest tests/ui/test_source_primary_cycle.py tests/ui/test_issue77_wp_c_quick_compare.py tests/ui/test_issue77_wp_c_review_regressions.py tests/ui/test_multiview_arrangements.py tests/ui/test_p1d_multiview_polish.py -q` | **61 passed in 27.27s** before added regressions |
| `.venv/Scripts/python.exe -m mypy src` | Success: no issues found in **108 source files** |
| `.venv/Scripts/python.exe -m pip check` | No broken requirements found |
| `.venv/Scripts/python.exe scripts/check_docs.py` | Documentation contract passed |
| `.venv/Scripts/python.exe -m mkdocs build --strict` | Documentation built successfully; Material emits an upstream informational notice |
| `git diff origin/main...HEAD --check` | Exit 0 after Markdown whitespace repair |

Ruff tracked-file validation used PowerShell:

```powershell
$trackedPython = @(git ls-files '*.py' | Where-Object { Test-Path -LiteralPath $_ })
.\.venv\Scripts\python.exe -m ruff check @trackedPython tests/ui/test_source_primary_cycle_runtime.py
.\.venv\Scripts\python.exe -m ruff format --check @trackedPython tests/ui/test_source_primary_cycle_runtime.py
```

Both passed; format reported **352 files already formatted**. The unfiltered
`ruff check .` / `ruff format --check .` result remains 4 lint / 3 format issues
solely in the three pre-existing untracked GC diagnostic scripts listed above.
They were deliberately not modified or committed.

## Diagnostic limitation

The successful full-run log contains one `0x8001010d` Windows diagnostic at the
pytest-qt `app.processEvents()` hook. The process subsequently completed all 1567
tests with exit 0. This is **not evidence of a terminated process**. CPython
3.10.11's [vectored exception handler](https://github.com/python/cpython/blob/v3.10.11/Modules/faulthandler.c#L392-L432)
prints the fatal-exception heading before returning `EXCEPTION_CONTINUE_SEARCH`;
the observed continuation and exit 0 establish non-termination in this run.
The native emitter/root cause remains unidentified; no blanket claim of an
exception-free Windows environment is made. No exception suppression, GC changes,
test skips, timeout inflation or lifecycle weakening was introduced.

The first sandbox full attempt is not completion evidence: restricted Git,
clipboard/settings and Session persistence failed, and that attempt was stopped.
Only the native-access full run establishes the full pytest PASS above.

## Completion and provenance

- Fixed the independently reproduced obsolete Blink test; added current T/gain,
  Difference, ROI, Selected order and keyboard-focus regression coverage.
- Changed files in this repair pass: retired `test_issue77_wp_c_blink_runtime.py`,
  added `test_source_primary_cycle_runtime.py`, extended `test_source_primary_cycle.py`,
  updated `docs/CURRENT_STATE.md`, and this validation record.
- Native visual/key checks are recorded in Progress; no D&D behavior was changed.
  The temporary manual launcher was removed and was never committed. Ignored local
  diagnostic logs remain available in `temp/` without becoming product architecture.
- Independent reviewer issued **PASS** after inspecting the repaired source/tests,
  full-run completion, the unsuppressed diagnostic and the final documentation.
  Their earlier independent related-UI run passed 58 tests in 34.24 seconds on
  `9c2f09f`; they directly reran docs/diff checks during final review.
- Agent commits use the configured `mc.kang` author/committer with
  `Co-authored-by: ChatGPT <noreply@openai.com>`. GitHub activity uses verified
  owner account `delphykmc`; the PR body is marked ChatGPT-assisted. Existing human
  commits were preserved, including the two remote documentation/whitespace commits.
- Remaining limitation: unidentified non-terminating COM diagnostic noted above.
  No functional source-cycling work is deferred. PR state records the actual merge.
