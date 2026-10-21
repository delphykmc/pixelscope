# Execution plan: pytest checkout import authority

Status: Complete

Owner: ChatGPT, requested by repository owner

Branch/PR: `codex/pytest-checkout-import`; pull request targets `main`

Last updated: 2026-10-22

## Goal and scope

Investigate the owner's 13 source-cycle failures on main and correct any reproduced
defect. Preserve T rotation, retired Blink, gain, ROI and Difference semantics.
Application packaging, dependencies, unrelated diagnostics and Git history are excluded.

## Findings

- Baseline is `main@3805eba`. The pasted run reports 13 failed and 1554 passed:
  `MainWindow.cycle_primary_source` is missing and `_blink_snapshot` still exists.
  Both observations describe pre-retirement implementation state.
- Current source includes the method and removes Blink. The local CPython 3.10.11
  interpreter imports this checkout's source. The two affected modules passed
  **14 tests in 11.48s** before edits. The original failing process's import path
  was not recorded, so its exact environment cause cannot be established.
- Pytest had no checkout source-path setting. A subprocess regression with an
  external `pixelscope` package on `PYTHONPATH` reproduced incorrect import origin:
  **1 failed in 1.83s** before the fix.

## Implementation and validation

- Add `pythonpath = ["src"]` to the existing pytest configuration. This makes the
  test source authority independent of a stale external package/editable checkout.
- Add `tests/integration/test_pytest_source_import.py` to exercise actual pytest
  import resolution in a subprocess with a competing external package.
- Document test source authority in `docs/QUALITY.md`. No product source changes.
- Focused regression plus both source-cycle modules: **15 passed in 12.23s**.
- Focused Ruff check/format, docs and whitespace checks passed.
- An initial restricted full run was interrupted after early failures; it is not
  completion evidence. Final native-access Windows validation with normal GC:
  `.venv/Scripts/python.exe -m pytest -q` completed with **1568 passed in 392.75s**,
  exit 0. This includes the new subprocess regression and both source-cycle modules.
- `.venv/Scripts/python.exe -m mypy src`: **Success: no issues found in 108 source
  files**. `.venv/Scripts/python.exe -m pip check`: **No broken requirements found**.
- Ruff check on tracked Python files plus the new regression passed; Ruff format
  reported **353 files already formatted**. Unfiltered `ruff check .` still reports
  **4 errors** in pre-existing untracked `diagnose_gc_pre569.py` and
  `diagnose_gc_survivors.py`; `ruff format --check .` reports **3 files would be
  reformatted**, all pre-existing untracked `scripts/diagnose_gc_*.py` files.
  These unrelated diagnostics were preserved.
- `.venv/Scripts/python.exe scripts/check_docs.py`: **Documentation contract passed**.
  `git diff --check`: exit 0. Durable-document changes are additive, with no removed
  baseline contract text.

## Outcome and constraints

Changed files: `pyproject.toml`, `tests/integration/test_pytest_source_import.py`,
`docs/QUALITY.md`, and this record. Current main's product failure did not reproduce;
the confirmed test source-selection weakness is corrected without changing product
behavior or weakening assertions. No functional follow-up is deferred.
Do not infer the original process's source path from a later successful run.
No new manual GUI check has been performed; existing source-cycle tests retain
actual Qt key-event, rendered-preview, gain, ROI and Difference assertions.
Publication uses the verified owner account `delphykmc`. Agent commits use the
configured `mc.kang` identity with `Co-authored-by: ChatGPT <noreply@openai.com>`;
the pull request body is marked ChatGPT-assisted. Existing human history is untouched.
