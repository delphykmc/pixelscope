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
git diff --check
```

Use narrower tests during development. Before completion, run the full applicable
suite. If a command cannot run, record the exact command, failure, reason, and
unverified risk.

For P2-F performance characterization, run the observational performance slice
with output enabled before the full repository contract:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -s tests\performance
```

Timing output from this command is characterization evidence only. PASS/FAIL must
come from deterministic correctness, resource, request/lifecycle, and bounded-
ownership assertions rather than an elapsed-time threshold.

## Change-to-check matrix

| Change | Required evidence |
|---|---|
| Numerical/image-processing logic | Unit tests for dtype, promotion, bounds, channel semantics, overflow, non-contiguous arrays, and edge cases |
| Qt state/interaction | Focused UI test plus relevant smoke test; manual Windows check for visual/timing-sensitive behavior |
| Worker/cache/asynchronous lifecycle | Tests for request identity, queued/running distinction, authority transition, stale-result rejection, cancellation/invalidation, generation changes, and bounded resources |
| File/RAW decoding | Valid, malformed, truncated, unsupported, endian, stride, alignment, packing, bit-depth, profile identity, and exact-size policy cases as applicable |
| Persistence/QSettings | Fresh-state, saved-state, invalid/legacy-state, schema migration/future-version behavior, reset scope, and restart behavior |
| Performance/resource characterization | Representative FHD/UHD and dtype/channel/RAW cases; exact native bytes, cache/residency state, worker ownership, decode count, stale rejection, and output correctness as merge gates; wall-clock timings observational only |
| Application identity/package resources | Focused SVG/PNG/ICO structure and decode tests, application-icon UI test, reproducible-generation check, wheel-content verification, unrelated-CWD launch, and Windows title-bar/Alt+Tab/running-taskbar/DPI visual checks |
| Public workflow/terminology | Product/user documentation update and UI assertions |
| Dependency/packaging | Python 3.10 evidence, `pip check`, packaging-constraint review, and explicit authorization before packaging tools run |
| Documentation/harness | `scripts/check_docs.py`, consistency with current code/PR scope, provenance disclosure when agent-assisted, and diff inspection |

## P3-D unified input validation contract

P3-D treats registration, selection, presentation, and decoded-source residency as
separate observable states. Tests must not use the six-tile presentation limit as
a registration limit.

Deterministic focused coverage must establish:

- Open Images multi-file input registers every supported direct file and selects
  those direct files; more than six direct files remain registered/selected while
  presentation stays bounded by the existing viewer capacity.
- Open Folders supports multiple directories, deterministic resolved-path
  deduplication, and registration counts above six; folder registration does not
  auto-select a first image or create an implicit comparison group.
- Folder D&D is registration-only for one, two, six, and greater-than-six folder
  counts; direct image D&D is register + select; mixed D&D selects only explicit
  direct files while registering folder contents.
- `documents > 0` with zero selected documents is stable and presents the
  registered-but-unselected workspace message without decode/render failure.
- PageUp/PageDown Folder Position derives only from currently selected one-to-six
  distinct folders; unrelated registered folders do not participate.
- Folder-only registration preserves selection, layout/presentation, active/focus
  state, ROI, Line Profile, Difference presentation/cache, Display Gain,
  source-residency ownership, and unrelated worker/decode state where applicable.
- Folder RAW registration does not open a profile-dialog sequence or guess
  metadata. Deterministic same-basename sidecar identity is retained, profile
  resolution occurs when foreground loading actually requires the RAW, and
  unresolved RAW is not speculatively preloaded.
- Unsupported files and standalone JSON are ignored; folders with no supported
  images do not make other selected folders fail registration.

Owner/manual Windows checks must include the same intent split through File-menu
and drag/drop paths, including a large registered catalog while an existing
comparison remains active.

## Golden paths

Preserve deterministic fixtures and smoke paths for:

- Standard image and unpacked RAW loading.
- MIPI RAW10/12/14 decoding and packed/unpacked equivalence.
- RAW exact-size policy through `MainWindow` → worker → reader, including
  oversized relaxed/exact behavior and matching JSON-sidecar auto-approval.
- Unified P3-D input ownership: selection-oriented direct images,
  registration-oriented folders, >6 catalog registration, mixed D&D, lazy folder
  RAW profile resolution, registered-but-unselected workspace, and selected-only
  Folder Position.
- Ordered selection, folder navigation, and fixed one-to-six-image layouts.
- Folder Position planning for one-to-six selected distinct folders, atomic
  endpoint no-op, natural ordering, and predicted PageDown/actual target equality.
- Keyboard separation: Files Up/Down rows, Left/Right selected-image activity,
  and PageUp/PageDown Folder Position membership.
- Shared cursor, zoom, ROI, Histogram, and Line Profile behavior.
- Repeated Single View number-key navigation across an unchanged selected set must
  not restart an identical Statistics/Histogram request, flash **Preparing
  analysis...**, cancel/recreate the same in-flight numerical worker, or rerender
  a completed identical result. ROI, histogram-bin, generation/source-identity,
  channel-layout, or Bayer-pattern changes remain valid recomputation triggers.
- Difference calculation, cache reuse/eviction, metrics, display-only updates,
  and startup cache-budget injection.
- P3-A Difference family/domain semantics: Gray-only channel exposure; RGB/RGBA
  alpha exclusion; same-CFA Bayer; cross-family/size/CFA rejection; native compact
  uint8/uint16 regression; mixed-bit independent full-scale normalization to
  float32 `[0,1]`; `%FS` strict-mask threshold; domain-aware reversed-pair cache
  restore; short validation status plus detailed tooltip; and Settings schema-v5
  native Threshold/Gain live-apply regression.
- P3-A normalized memory behavior: no full-size float64 normalized map, no
  full-size squared-error map, and no full-size float64 percentile copy. P95/P99
  use a fixed 65,536-level normalized histogram and must remain within `1/65535`
  full scale of the corresponding quantile.
- Decoded-source exact-byte accounting, deterministic LRU/protection, soft
  over-budget and oversized-source behavior, eviction invalidation, Files badge
  state, existing-path reload, and stale-result rejection.
- Settings fresh state, round-trip, schema-v4-to-v5, schema-v3 and older migration,
  legacy RAW migration, corrupt-state recovery, future-schema protection, and reset
  separation from workspace persistence.
- General / Files / Performance Settings page navigation, Settings-only RAW
  preference ownership, RAW don't-show partial-update preservation, optional
  default Open/Export locations, last-used-folder fallback, and Difference Map
  Cache/Decoded Source Memory/preload independent and combined restart indication.
- Persisted Difference Threshold/Gain startup injection and live Settings-save
  propagation without restart-required state.
- Split-channel loading placeholders and stale-result rejection.
- Plots visibility, selected tab, floating/docked/maximized state, and workspace
  restoration.
- Resident-image byte-budget eviction and reload, including more than seven
  resident sources when their bytes fit.
- Exactly-one-position preload, foreground-idle start, separate max-one pool,
  resident reuse, disabled runtime, rapid navigation, plan replacement,
  worker-lifetime-bounded cancellation de-duplication, late-result rejection,
  removal/generation/profile races, RAW exact-size/profile reuse, silent retryable
  failure, and ordinary low-budget residency eviction without a reload loop.
- Running-preload promotion acceptance only after the worker's `started` signal;
  queued/not-started, cancelled, stale, generation/path/profile/exact-policy/token
  mismatch, already-resident, or duplicate-normal-load cases must not promote.
- Promotion once-only ownership: a matching RUNNING next target becomes logical
  foreground authority before old-plan invalidation, leaves speculative
  cancellation ownership, becomes foreground Loading/protected state, and starts
  no second decoder for the same source.
- Promoted success uses normal foreground result application exactly once,
  including exact native `source.nbytes` residency accounting, MRU touch, Files
  residency state, selected-batch render gating, ordinary eviction, and Ready
  status. Deterministic tests assert duplicate decode count rather than elapsed
  time.
- Promoted failure uses normal foreground error/status and P2-D
  `foreground-load/decode` failure diagnostics exactly once; it must not also
  increment speculative preload failure history.
- Rapid navigation away from a promoted decode requests foreground cancellation,
  invalidates token authority, and deterministically rejects a late completion
  even when cancellation cannot stop the decoder.
- Pair/group navigation with preload concurrency one: one exact RUNNING member may
  be promoted while the remaining required members use the normal pool; selected
  batch rendering waits for all required foreground authorities.
- RAW promotion preserves exact registered `RawProfile` identity and exact-size
  policy without speculative dialogs or duplicated RAW decode logic.
- Promotion does not change preload direction/depth/concurrency: still `+1`,
  exactly one Folder Position, max-one preload pool, max-two normal pool, no
  previous/bidirectional/next-next work, and no new Performance setting.
- Frozen deterministic runtime diagnostics over exact source/cache/worker/preload
  values; foreground/preload stale and failure instrumentation; stale cancelled or
  replanned preload failures excluded from recent failure history; bounded failure
  history; Windows/POSIX path, complete credential-assignment, bearer, traceback,
  multiline, and truncation sanitization; and repeated observation without LRU,
  worker, preload, selection, render, or filesystem mutation.
- Promotion diagnostics expose `promotion_count` / **Promoted to foreground: N**.
  A promoted physical preload worker is classified once as logical foreground and
  excluded from speculative preload active counts; diagnostics reads remain
  observation-only.
- **Help > Copy Diagnostics** remains the only diagnostics product surface: old
  Diagnostics dialog absent, clipboard text exactly equals the canonical formatter
  output, a short status-bar confirmation is shown, repeated unchanged copies are
  identical and timestamp-free, registered paths/credentials/traceback/image
  content are excluded, and copying starts/cancels no work or runtime mutation.
- Canonical application-icon loading from package resources independent of CWD.

Add a focused fixture when a bug depends on pixel values, bit depth, Bayer layout,
geometry, memory pressure, or event order. Keep fixtures small unless resolution or
memory behavior is the subject of the test.

## P3-A deterministic Difference contract

P3-A acceptance is value/resource based rather than timing based. Focused core,
cache, UI, and integration tests must establish the exact Gray/RGB/Bayer family
rules, effective-bit-depth domain selection, native representation regression,
known normalized full-scale/fractional values, float32 normalized output, bounded
metric allocation form, domain metadata under reversed-pair reuse, and `%FS`
threshold conversion. Representative large-image tests assert values/dtype and
allocation policy without an elapsed-time threshold.

The normalized P95/P99 contract is intentionally deterministic and approximate:
a 65,536-level histogram covers `[0,1]`, so quantile error is bounded by one
histogram step (`1/65535` FS). MAE/MSE/RMSE are accumulated from bounded chunks
and are not histogram-quantized. Native integer percentile semantics remain exact
through the existing integer histogram path.

Owner/local Windows checks cover Gray Difference, mixed-bit normalized Difference,
`%FS` masks, compact validation/tooltips, same-bit native regression, cached and
reversed-pair reuse, and six-source Difference Single View. Packaging tools are
not part of P3-A.

## P2-F deterministic characterization contract

The final P2 automated matrix is representative rather than Cartesian:

| Scenario | Primary contract |
|---|---|
| FHD RGB uint8 | native byte count, RGB histogram counts, preview/difference/mask shape and dtype, zero self-difference |
| FHD grayscale uint16 | native byte count, Gray histogram count, preview, promoted signed dtype, compact absolute dtype, zero self-difference |
| UHD Bayer uint16 profile-described RAW | production RAW/Bayer preview path, Auto 4096-bin RGGB CFA analysis, exact plane counts/content, native bytes, difference metrics, threshold mask |
| Single View repeated Statistics request | identical completed/in-flight request is a no-op; changed ROI/request identity cancels/replaces obsolete work |
| Existing real 4K RGB + RGGB10-u16 RAW fixture | reader/RAW integration and expected image/difference metrics without adding a new large binary fixture |

`tests/performance/test_performance_smoke.py` may print `perf_counter()` timings
for raw-document load/Bayer analysis/difference/metrics/threshold-mask work. No
timing number is a merge gate. The removed historical `threshold_mask < 0.5`
assertion must not be replaced with another arbitrary hardware/load threshold.

P2-wide audit evidence remains distributed through the focused suites rather than
duplicated into one mega-test:

- Settings repository/schema tests cover defaults, current round-trip, v4-to-v5,
  v3/current and older migration, old-valid Difference-cache clamp,
  malformed/invalid state, legacy RAW, future-schema read-only behavior, reset
  scope/workspace preservation, restart semantics, enabled preload, and the
  combined RAM guard at/above its exact boundary.
- Residency/Difference tests cover exact native `source.nbytes`, protected and
  ordinary LRU, low/soft/oversized budgets, reload/no-loop behavior, separate
  Difference budget/accounting, and Difference independence under source pressure.
- Preload/promotion tests cover immediate resident/completed reuse, RUNNING exact
  promotion with one decode, ordinary foreground fallback, exactly-once success
  and failure, pair/group completion, RAW identity/exact-size, logical diagnostics
  classification, no new speculation while a promoted worker owns the max-one
  preload pool, and rapid-navigation stale rejection.
- Diagnostics tests cover exact source/Difference/worker/preload values, promotion
  count, bounded sanitized failures, Copy Diagnostics only, and observation-only
  reads/copies with no LRU, load, preload, cancellation, render, or filesystem
  side effect.
- `tests/ui/test_p2f_analysis_request_dedup.py` covers completed identical-request
  no-op, in-flight worker preservation without cancellation, and changed-request
  cancellation/restart.

Process RSS accounting, live monitoring, telemetry, benchmark UI, preload policy
expansion, new settings/schema, and native optimization are outside P2-F.

## P2-F Windows characterization matrix

Owner/local Windows validation is the authoritative manual closure evidence for
P2-F. Check at minimum:

1. FHD RGB normal navigation.
2. UHD/uint16 navigation.
3. Bayer/RAW navigation.
4. Pair/group PageDown.
5. Already-resident transition.
6. Completed-preload transition.
7. RUNNING-preload promotion.
8. Rapid repeated PageDown.
9. Low source-memory budget.
10. Oversized required source.
11. Difference cache under source pressure.
12. Settings restart semantics.
13. **Help > Copy Diagnostics**.
14. Statistics / Histogram / Line Profile / Difference / Split Channels regression,
    including repeated number-key switching in Single View without Statistics
    preparation churn for an unchanged selected set.

The manual gate is absence of visible stall/regression, incorrect reload,
duplicated-load symptoms, unnecessary identical analysis restart/cancellation,
error/state corruption, or workflow breakage. Any collected timing numbers are
hardware-specific observational evidence only.

The repository has no GitHub Actions workflow. P2-F does not introduce a Windows
CI gate without first observing PySide6/pytest-qt/offscreen reliability and
acceptable suite runtime/resource use on the target runner. Windows CI
introduction is therefore deferred; packaging/installer CI remains P7.
