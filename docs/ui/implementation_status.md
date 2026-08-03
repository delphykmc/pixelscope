# PixelScope UI/performance iteration status

## Baseline

- Original iteration baseline: `ea64b1d8fda331e3f85dbfa0181d772974358e74`
- Initial P0-A commit: `d66b371831b4f2fa2792f9a5f576b1d66f4ba19c`
- P0-A correction merge: `1606503a08b24b73e77f9fb4784d22c2339d6f59`
- Current work branch: `feat/p0b-difference-cache-metrics`
- Current phase: **P0-B — absolute Difference cache and metrics**
- Phase state: **implementation complete; awaiting Windows test and review**
- Runtime constraints retained: CPython 3.10, PySide6 6.4.2, and future
  PyInstaller 5.7 `onedir` compatibility.

## Completed in P0-B

### Difference map cache

- Replaced the unbounded Difference map dictionary with a dedicated
  `DifferenceMapCache` byte-budget LRU.
- Uses `ndarray.nbytes` for accounting.
- Default cache ceiling is centralized at **512 MiB**.
- The cache budget is constructor-injected and the cache does not read
  `QSettings` or depend on Preferences UI.
- Exposes read-only diagnostics:
  - `budget_bytes`
  - `used_bytes`
  - `entry_count`
- Keeps the existing order-independent source-pair and document-generation key.
- LRU access promotes reused maps.
- Inserting a map evicts least-recently-used entries until the byte ceiling is
  satisfied.
- A single map larger than the cache budget is calculated and displayed but is
  not retained.
- Entries that reference a known document at an older generation are removed.
- Metric and preview caches derived from an evicted map are removed with it.

### Difference metrics

- The Difference metrics table now shows:
  - MAE
  - MSE
  - RMSE
  - PSNR
  - P95
  - P99
  - Max difference
  - Non-zero ratio
- Removed the user-facing minimum-difference metric.
- Native uint8/uint16 absolute maps use chunked processing and an exact native
  histogram with at most 65,536 bins.
- MAE, MSE, RMSE, PSNR, P95, P99, maximum, and non-zero ratio are calculated
  exactly for the supported native integer path.
- The metric path no longer creates full-resolution float64 and squared-map
  temporaries for native Difference maps.
- Full-image, ROI, RGB channel, combined RGB, Bayer mosaic, and Bayer plane
  selection continue to derive from the same compact absolute map.
- Absolute and Mask remain the only Difference display modes in this phase.
  Existing core signed-difference utilities remain available but are not exposed
  in the UI.

### Architecture preparation

- Added an immutable `PerformanceSettings` model with the centralized
  Difference cache default.
- Added a core cache module independent of Qt widgets and settings persistence.
- `DifferencePanel` accepts the cache budget at construction and exposes the
  cache object for diagnostics.
- Preferences, runtime budget changes, image resident cache, and preload are not
  implemented in P0-B.

## Files changed in P0-B

- `src/pixelscope/core/performance_settings.py`
- `src/pixelscope/core/difference_cache.py`
- `src/pixelscope/core/diff_engine.py`
- `src/pixelscope/ui/difference_panel.py`
- `tests/unit/test_difference_cache.py`
- `tests/unit/test_difference_metric_chunks.py`
- `tests/ui/test_difference_cache_panel.py`
- `tests/performance/test_performance_smoke.py`
- `docs/ui/implementation_status.md`

## Test coverage added

- 512 MiB centralized default and invalid budget rejection.
- Byte accounting, LRU promotion, LRU eviction, oversized-map behavior, and
  explicit removal.
- Stale document-generation eviction while unrelated pairs remain cached.
- Exact chunked uint16 statistics compared with direct NumPy results.
- Non-contiguous channel views and ROI metric bounds.
- Zero-map infinite PSNR and zero non-zero ratio.
- Guard against reintroducing `np.square` in the native chunked metric path.
- DifferencePanel cache-budget injection and diagnostics.
- Metric-table labels and rendered values.
- Dependent metric-cache eviction when a map leaves the LRU.
- Existing 4096×3072 performance smoke now executes chunked Difference metrics.

These tests were added through the GitHub connector and have not yet been run in
the user's Windows/PySide6 environment.

## Required local validation

Fetch the branch and run:

```powershell
git fetch origin
git switch feat/p0b-difference-cache-metrics
git pull --ff-only

.\.venv\Scripts\python.exe -m pytest tests\unit\test_difference_cache.py -q
.\.venv\Scripts\python.exe -m pytest tests\unit\test_difference_metric_chunks.py -q
.\.venv\Scripts\python.exe -m pytest tests\ui\test_difference_cache_panel.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
```

Manual UI checks:

1. Calculate an RGB Difference and confirm all eight metrics are populated.
2. Switch Full image/Active ROI and verify metrics refresh without recalculating
   the absolute map.
3. Switch All/R/G/B and verify the cached map is reused.
4. Change Gain and Mask threshold and verify only the display preview updates.
5. Swap Image 1/Image 2 and verify the same absolute map is reused.
6. Re-select a previously calculated pair and verify cached restoration.

## Incomplete / intentionally deferred

- P0-C toolbar icon and state work: not started.
- P1-A through P1-C: not started.
- Preferences UI and QSettings-backed performance settings: separate future
  phase; memory settings take effect after restart.
- Image resident cache and one-group-ahead preload: separate future phase.
- GitHub Release update checking and installer workflow: separate future phase.
- Legacy visible A/B and `_compare_pair` behavior remains for the P1-A audit.
- P0-A's internal fixed-arrangement compatibility field/QSettings key remains for
  a later cleanup.

## Exact next starting point

1. Run the P0-B targeted and full validation commands on Windows.
2. Apply any test, type, formatting, or UI corrections on
   `feat/p0b-difference-cache-metrics`.
3. Create and review a P0-B pull request after validation passes.
4. Merge P0-B.
5. Start **P0-C — toolbar icon/state work** from the merged P0-B commit.
