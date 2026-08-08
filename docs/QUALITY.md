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
| Persistence/QSettings | Fresh-state, saved-state, invalid/legacy-state, schema migration/future-version behavior, reset scope, and restart behavior |
| Application identity/package resources | Focused SVG/PNG/ICO structure and decode tests, application-icon UI test, reproducible-generation check, wheel-content verification, unrelated-CWD launch, and Windows title-bar/Alt+Tab/running-taskbar/DPI visual checks |
| Public workflow/terminology | Product/user documentation update and UI assertions |
| Dependency/packaging | Python 3.10 evidence, `pip check`, packaging-constraint review, and explicit authorization before packaging tools run |
| Documentation/harness | `scripts/check_docs.py`, consistency with current code/PR scope, provenance disclosure when agent-assisted, and diff inspection |

For application identity changes, run the generator in check mode and verify the
built wheel contains the canonical triplet:

```powershell
.\.venv\Scripts\python.exe scripts\generate_icon_assets.py --check
Remove-Item -Recurse -Force .tmp-wheel -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pip wheel . --no-deps -w .tmp-wheel
.\.venv\Scripts\python.exe scripts\check_wheel_icon_assets.py .tmp-wheel
```

Source-run title-bar, Alt+Tab, running-taskbar, scaling, and taskbar-background
checks belong to P2-A1. Executable-file, pinned-shortcut, installer-shortcut, and
final packaged-shell identity belong to P7.

## Golden paths

Preserve deterministic fixtures and smoke paths for:

- Standard image and unpacked RAW loading.
- MIPI RAW10/12/14 decoding and packed/unpacked equivalence.
- RAW exact-size policy through `MainWindow` → worker → reader, including
  oversized relaxed/exact behavior and matching JSON-sidecar auto-approval.
- Ordered selection, folder navigation, and fixed one-to-six-image layouts.
- Shared cursor, zoom, ROI, Histogram, and Line Profile behavior.
- Difference calculation, cache reuse/eviction, metrics, display-only updates,
  and startup cache-budget injection.
- Decoded-source exact-byte accounting, deterministic LRU/protection, soft
  over-budget and oversized-source behavior, eviction invalidation, Files badge
  state, existing-path reload, and stale-result rejection.
- Settings fresh state, round-trip, schema-v3-to-v4 and older migration, legacy
  RAW migration, corrupt-state recovery, future-schema protection, and reset
  separation from workspace persistence.
- General / Files / Performance Settings page navigation, Settings-only RAW
  preference ownership, RAW don't-show partial-update preservation, optional
  default Open/Export locations, last-used-folder fallback, and Difference Map
  Cache/Decoded Source Memory independent restart indication.
- Persisted Difference Threshold/Gain startup injection and live Settings-save
  propagation without restart-required state.
- Split-channel loading placeholders and stale-result rejection.
- Plots visibility, selected tab, floating/docked/maximized state, and workspace
  restoration.
- Resident-image byte-budget eviction and reload, including more than seven
  resident sources when their bytes fit.
- Canonical application-icon loading from package resources independent of CWD.

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
9. Actual agent provenance: observed author/committer, co-author fallback if
   used, account used for GitHub comments/reviews, and confirmation that existing
   human commits were not rewritten.

Do not claim a check passed unless its output was observed. Generated code
volume and commit count are not quality signals.
