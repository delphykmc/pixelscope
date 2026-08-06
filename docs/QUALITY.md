# Quality and completion contract

A change is complete only when observable behavior is specified, mechanically
checked where practical, and reported with evidence that was actually observed.

## Standard validation

Run from the repository root with the pinned CPython 3.10 environment:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
```

Use narrower tests during development. Before completion, run the full
applicable suite. If a command cannot run, record the exact command, failure,
reason, and unverified risk.

## Change-to-check matrix

| Change | Required evidence |
|---|---|
| Numerical/image-processing logic | Unit tests for dtype, promotion, bounds, channel semantics, overflow, non-contiguous arrays, and edge cases |
| Qt state/interaction | Focused UI test plus relevant smoke test; manual Windows check for visual/timing-sensitive behavior |
| Worker/cache/asynchronous lifecycle | Tests for request identity, stale-result rejection, cancellation/invalidation, generation changes, and bounded resources |
| File/RAW decoding | Valid, malformed, truncated, unsupported, endian, stride, alignment, packing, and bit-depth cases as applicable |
| Persistence/QSettings | Fresh-state, saved-state, invalid/legacy-state, reset, and restart behavior |
| Public workflow/terminology | Product/user documentation update and UI assertions |
| Dependency/packaging | Python 3.10 evidence, `pip check`, packaging-constraint review, and explicit authorization before packaging tools run |
| Documentation/harness | `scripts/check_docs.py`, consistency with current code/PR scope, and diff inspection |

## Golden paths

Preserve deterministic fixtures and smoke paths for:

- Standard image and unpacked RAW loading.
- MIPI RAW10/12/14 decoding and packed/unpacked equivalence.
- Ordered selection, folder navigation, and fixed one-to-six-image layouts.
- Shared cursor, zoom, ROI, Histogram, and Line Profile behavior.
- Difference calculation, cache reuse/eviction, metrics, and display-only
  updates.
- Split-channel loading placeholders and stale-result rejection.
- Plots visibility, selected tab, floating/docked/maximized state, and workspace
  restoration.
- Resident-image eviction and reload.

Add a focused fixture when a bug depends on pixel values, bit depth, Bayer
layout, geometry, memory pressure, or event order. Keep fixtures small unless
resolution or memory behavior is the subject of the test.

## Completion evidence

Every agent-assisted change reports:

1. Changed files and purpose.
2. Observable behavior added, changed, or intentionally preserved.
3. Explicit in-scope and out-of-scope items.
4. Commands run and exact pass/fail results.
5. Manual checks and environment.
6. Known limitations, deferred work, and unverified areas.
7. Product, architecture, decision, roadmap, current-state, or execution-plan
   updates.
8. Removal or retention rationale for temporary scripts and compatibility paths.

Do not claim a check passed unless its output was observed. Generated code
volume and commit count are not quality signals.
