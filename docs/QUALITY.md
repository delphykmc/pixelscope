# Quality and completion contract

A change is complete only when its behavior is specified, mechanically checked where practical, and reported with evidence.

## Validation commands

Run from the repository root with the pinned CPython 3.10 environment:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pip check
```

Run narrower tests during development, but run the full applicable suite before completion. If a command cannot run, record the command, exact failure, and what remains unverified.

## Change-to-check matrix

| Change | Required evidence |
|---|---|
| Numerical or image-processing logic | Unit tests covering dtype, bounds, channel semantics, overflow, non-contiguous arrays, and representative edge cases |
| Qt state or interaction | Focused UI test plus relevant smoke test; manual Windows check for visual or timing-sensitive behavior |
| Worker, cache, or asynchronous lifecycle | Tests for stale-result rejection, generation changes, cancellation or invalidation, and bounded resources |
| File or RAW decoding | Valid, malformed, truncated, unsupported, endian, stride, and bit-depth cases as applicable |
| Public workflow or terminology | Product/user documentation update and UI assertions |
| Dependency or packaging | Python 3.10 compatibility evidence, `pip check`, packaging-constraint review, and explicit user authorization before packaging tools run |
| Documentation only | Link/path review, consistency with current code and decisions, and diff inspection |

## Golden paths

Preserve deterministic fixtures and smoke paths for the workflows most likely to regress:

- Standard image and unpacked RAW loading.
- Ordered multi-image selection and 1–6 image layouts.
- Shared cursor, zoom, ROI, histogram, and line profile behavior.
- Difference calculation, cache reuse, metrics, and display-only updates.
- Loading placeholders and stale-result rejection.
- Workspace persistence and restoration.

Add a focused golden fixture when a bug depends on specific pixel values, bit depth, Bayer layout, geometry, or event order. Keep fixtures small unless resolution or memory pressure is the behavior under test.

## Completion report

Every agent-assisted change should report:

1. Changed files and their purpose.
2. Observable behavior added, changed, or intentionally preserved.
3. Commands run and exact pass/fail results.
4. Manual checks performed and environment used.
5. Known limitations, deferred work, and unverified areas.
6. Documentation or decision records updated.

Do not claim a check passed unless its output was observed. Do not use generated code volume or number of commits as a quality signal.
