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

Use narrower tests during development. Before completion, run the full
applicable suite. If a command cannot run, record the exact command, failure,
reason, and unverified risk.

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
| External artifact persistence | Schema/kind/version validation, deterministic identity, atomic save, corrupt/future/semantic-invalid rejection before workspace mutation, missing/zero-loadable behavior, round-trip ordering/state, privacy/portability implications, and explicit non-ownership of runtime resources |
| Typed recent-entry history | Per-type MRU/bounds/restart persistence, canonical input delegation, meaningful-success promotion, missing Remove/Keep, existing-unusable/wrong-kind retention, observer-failure isolation, privacy/reset scope, and real cross-feature artifact behavior |
| Performance/resource characterization | Representative FHD/UHD and dtype/channel/RAW cases; exact native bytes, cache/residency state, worker ownership, decode count, stale rejection, and output correctness as merge gates; wall-clock timings observational only |
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
- Folder Position planning for one-to-six distinct registered folders, atomic
  endpoint no-op, natural ordering, and predicted PageDown/actual target equality.
- Keyboard separation: Files Up/Down rows, Left/Right selected-image activity,
  and PageUp/PageDown Folder Position membership.
- Shared cursor, zoom, ROI, Histogram, and Line Profile behavior.
- P4-A direct curation: first-Pick baseline capture and stable Pick affordance;
  Active/Primary/Pick separation; depressed Pick plus bright-yellow tile border;
  `1/2/6/7/15/50` Selected cases; cross-page Pick persistence; zero-pick Keep
  Selection disabled; baseline-order Keep Selection; non-picked registration
  retention; Clear Selection and external-Selected-mutation invalidation; derived
  Split/Difference identity rejection; pan/Ctrl+drag ROI/Shift+drag Line behavior
  not toggling Pick; exact Files selection/first-Active state after Keep Selection;
  and Pick/Unpick/Clear causing no source load, generation, residency/protection,
  preload, Difference-cache, or numerical-analysis authority change.
- P4-B Comparison Set persistence: deterministic `.pixelscope` v1 round-trip and
  saved order/Active/applicable Primary/layout; normalized absolute-path identity;
  rejection of blank/relative identities, wrong kind, future schema, invalid layout,
  invalid RawProfile, and corrupt JSON before registration/foreground load; logical
  Selected save semantics independent from temporary Picks; post-Keep curated save;
  atomic replace; partial-missing and zero-loadable behavior; later-page Active →
  derived Current Comparison Page → applicable Primary restore; resolved RAW
  metadata restore versus unresolved lazy RAW; large-set page-bounded foreground
  load/protection; and Save causing no `_ensure_loaded`, residency/protection/LRU,
  preload, Difference/cache, Display Gain, or analysis ownership change.
- P4-C Recent Entries: typed Image/Folder/Comparison-Set MRU with ten-entry bounds,
  normalized absolute paths, real QSettings restart/clear persistence, and
  ApplicationSettings-v5/reset separation; production File/P4-B routing; meaningful
  success promotion; missing Remove/Keep with no workspace/Pick mutation;
  existing-invalid and other unusable retention; wrong-kind path retention without
  cross-intent reinterpretation; empty-folder promotion; failed-save non-recording;
  injected persistence/menu failure isolation; and real `.pixelscope` partial and
  zero-loadable opens through the P4-B loader with correct MRU and workspace state.
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

Add a focused fixture when a bug depends on pixel values, bit depth, Bayer
layout, geometry, memory pressure, or event order. Keep fixtures small unless
resolution or memory behavior is the subject of the test.

## P4-A deterministic curation contract

P4-A acceptance is state/ownership based rather than timing based. Focused Qt-free
state tests and production-composition UI tests must establish direct first-Pick
baseline capture, ID-only baseline/Pick Set lifetime, idempotent Pick/Unpick,
zero-pick safety, original-order Keep Selection, cross-page retention, stable Pick
checked/yellow visual state, and external logical Selected mutation invalidation.
There is no acceptance requirement for an explicit Review Select mode because the
product intentionally has no such mode.

Production UI coverage must also establish the direct presentation-row contract
`Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection`,
where `Selected N` is temporary Pick count; eligible native Multi View tiles expose
`Pick` with stable text; Single View and Split/Difference derived presentations do
not acquire independent Pick identity; pan, Ctrl+drag ROI, and Shift+drag Line
Profile gestures do not toggle Pick; and Keep Selection leaves the Files tree on
exactly the resulting subset with the first result Active.

Runtime regression must prove that Pick membership itself is inert with respect to
native source ownership. On representative large pending selections, only the
Current Comparison Page may cause ordinary foreground load/protection changes;
Pick/Unpick/Clear Selection must add no `_ensure_loaded()` call, source generation
change, residency byte/protection owner, LRU touch, Comparison Page/Pick preload,
Difference calculation/cache invalidation, or Statistics/Histogram/Line Profile
request churn. Off-page picked sources are allowed to be nonresident and
unprotected.

Derived Split/Difference presentation cannot become an independent Pick identity.
Settings schema remains v5, the captured baseline/Pick Set is not persisted, and
P4-B persistence is outside P4-A.

Owner/local Windows validation is authoritative for visual affordance, paging,
selection replacement, and cross-feature interaction. Run the focused P4-A suite
before the full repository contract:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_review_selection.py tests\ui\test_p4a_review_selection.py tests\ui\test_p4a_review_selection_review_fixes.py
```

## P4-B deterministic Comparison Set contract

P4-B acceptance is schema/transaction/ownership based rather than timing based.
The external v1 artifact boundary must establish:

- `.pixelscope` JSON with exact kind/schema version and same-version unknown-field
  tolerance;
- non-empty normalized absolute local source identities, with blank/relative
  persisted paths rejected before normalization;
- deterministic duplicate/member validation and atomic same-directory replacement;
- logical Selected save ordering, temporary Picks ignored until Keep changes logical
  Selected, and Save leaving curation state unchanged;
- complete semantic validation before any source registration or foreground load;
- partial missing-path load and zero-loadable no-mutation behavior;
- saved Active deriving the Current Comparison Page before an applicable page-local
  Primary/layout restore;
- resolved RAW metadata restored before foreground use while unresolved RAW remains
  lazy and Save does not force resolution;
- no persistence ownership of source arrays, source residency/LRU/protection,
  preload/promotion, Difference/cache, Display Gain, analysis requests/results,
  worker/token/generation state, derived documents, transient view state, ROI/Line,
  or P4-A Pick state;
- Settings schema remaining v5; and
- absolute-path privacy/portability implications documented in product/user docs.

Large pending-set tests must prove Save is metadata-only with respect to load and
residency authority. Large Open tests must prove foreground load/protection remains
bounded to the Active-derived Current Comparison Page rather than all logical
Selected members.

Run the focused P4-B suite before the full repository contract:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\unit\test_comparison_set.py `
    tests\ui\test_p4b_comparison_set.py
```

The repository owner reported `36 passed` for this focused P4-B command before PR
#30 merged. That historical report does not imply unobserved P4-C, docs, Ruff,
format, mypy, pip-check, `git diff --check`, or full-suite PASS.

## P4-C deterministic Recent Entries contract

P4-C acceptance is typed-path/delegation/persistence/ownership based rather than
timing based. Focused coverage must establish:

- independent Image/Folder/Comparison-Set MRU histories, ten-entry bounds,
  normalized absolute-path identity, deterministic dedup/order, and real QSettings
  restart persistence;
- `recent/*` namespace separation from ApplicationSettings schema v5 and Reset
  Settings, plus persistent Clear Recent Entries behavior;
- production routing through P3 image/folder authorities and P4-B save/open rather
  than ad-hoc workspace reconstruction;
- best-effort observer isolation so Recent storage/menu/callback failure cannot
  change canonical workflow success, Selected, residency/protection, or preload;
- meaningful-success promotion: Image after successful direct open, Folder after
  successful registration including empty folder, Comparison Set only for
  `loaded > 0`, and save only after successful atomic save;
- missing-path **Remove / Keep** with workspace/Pick preservation;
- existing-but-unusable retention and typed wrong-kind retention without
  cross-intent reinterpretation or MRU promotion;
- existing invalid `.pixelscope` retention;
- real P4-B partial-source Recent open with saved-order/Active/page/Primary/layout
  behavior, canonical partial warning, P4-A invalidation, and MRU promotion;
- real P4-B zero-loadable Recent open with workspace/Pick/MRU preservation and
  canonical zero-loadable feedback; and
- no ownership of source arrays, Current Comparison Page, residency/LRU/protection,
  preload, Difference/cache, Display Gain, analysis, worker/token/generation state,
  or temporary Picks.

Run the focused P4-C/P4-B regression slice before the full repository contract:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\unit\test_recent_entries.py `
    tests\ui\test_p4c_recent_entries.py `
    tests\ui\test_p4c_recent_entries_integration.py `
    tests\unit\test_comparison_set.py `
    tests\ui\test_p4b_comparison_set.py
```

No PASS is recorded for the current P4-C head until owner/local output is observed.

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