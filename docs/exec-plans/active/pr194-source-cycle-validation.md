# PR #194 source cycling validation and repair

Status: Active  
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
  the sandbox (2 passed in 3.86 seconds). Full normal-GC validation is now running
  with native Windows access. No timeout inflation, skip or GC workaround added.

## Completion

Pending final implementation, review and observed validation evidence.
