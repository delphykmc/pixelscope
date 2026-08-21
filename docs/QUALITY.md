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
- P4-C Session v1 and typed Recent: exact Registered/Selected/page-anchor/
  Active/Primary/layout/ROI/Line/Display Gain/Split and eligible-Difference intent;
  legacy Comparison Set v1 read compatibility; complete validation/staging before
  destructive replacement; zero-registered no-mutation; bounded current-page
  foreground reconstruction; explicit Calculate as the only restored Difference
  establishment path; typed max-10 Image/Folder/Session Recent delegation; and no
  persistence ownership of arrays/cache/residency/preload/workers/calculated
  analysis/Picks.
- P4-E focused export: exact current Histogram and Line Profile series serialized in
  deterministic source/channel/sample/bin order; Gray/RGB/Bayer and Full image/ROI
  context preserved; Statistics File-menu/toolbar parity and timestamped defaults;
  Difference metrics CSV plus Statistics/Difference table clipboard CSV; active
  Difference PNG requiring both matching active A/B provenance and a presentation
  key equal to the last settled preview key; stale A/B presentation re-entry staying
  unavailable until the current controls actually settle; filename semantics and PNG
  bytes describing that same presentation; no inactive/cached-only Difference
  promotion or recalculation; configured Export directory reuse; Cancel/write
  failure no workspace mutation; close/recreate safety for queued model callbacks
  and a physically running PNG worker; and no source generation,
  Selected/Active/Primary/Page, residency/preload, or Difference-cache ownership
  change.
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

The repository owner reported `36 passed` for this focused command on the current
runtime/test implementation. That report does not imply unobserved docs, Ruff,
format, mypy, pip-check, `git diff --check`, or full-suite PASS after later docs-only
commits.

## P4-C deterministic Session/Recent contract

P4-C acceptance is schema/transaction/reconstruction/observer based. Session v1
must preserve durable workspace intent without serializing runtime ownership.
Focused coverage establishes Registered and exact Selected membership/order,
Current Comparison Page anchor, applicable Active/Primary/layout, ROI/Line, Display
Gain/Split, RAW reconstruction metadata, and eligible current-page Difference recipe;
legacy Comparison Set v1 remains read compatible.

Open must parse once, reject semantically invalid artifacts before destructive
workspace mutation, stage incoming identities before removal, preserve the prior
workspace when zero incoming registrations succeed, foreground-load only the bounded
reconstructed page, and use the inherited source/Display Gain/ROI/Line/Split/
Difference paths. An eligible restored Difference recipe issues one explicit
Calculate and relies on the PR #33 result-ready path to establish active provenance.
Off-page hidden Difference provenance is not persisted.

Typed Recent Image/Folder/Session history is max-10 path-only observer metadata.
Activation delegates to canonical workflows, missing paths use Remove/Keep, and
bookkeeping failure cannot make a successful canonical operation fail. Settings
schema remains v5 and runtime arrays/cache/residency/preload/workers/calculated
analysis/Picks remain non-persistent.

P4-C is merged as PR #31 at
`436033a0d99513fe8db35f08305395127e430af2`; its previously reported owner Windows
validation belongs to that merged implementation and does not imply P4-E PASS.

## P4-E deterministic Analysis Export contract

P4-E acceptance is current-result/serialization/resource based, not timing based.
Export must consume existing canonical/result presentation data and never become an
analysis or source authority.

Focused coverage must establish:

- Statistics File-menu and toolbar Export entry points share the same timestamped
  controller path, suffix/error handling, and successful last-directory behavior
  while preserving Statistics CSV data semantics;
- Histogram CSV uses the exact current rendered series while preserving raw native
  counts/bin edges, current display bin edges/unit mode, deterministic source/
  series/channel ordering, and Full image/Active ROI context for supported Gray,
  RGB, and Bayer behavior;
- Line Profile CSV uses exact current rendered samples with deterministic
  line/source/series/channel/sample order and current X/Y mode semantics;
- Difference metrics CSV preserves source A/B, region, channel, comparison domain,
  effective source bit depths, metric identity, and deterministic numeric values;
  Statistics and Difference metric tables expose full-table CSV clipboard copy with
  headers without changing selected-cell Ctrl+C semantics;
- Difference PNG is unavailable without an explicitly established active result,
  current panel A/B must match active provenance, and the current presentation key
  `(pair/generation/domain/channel/mode/gain/threshold)` must match the last settled
  preview key before export is enabled or a dialog can open;
- `Calculate A/B → uncached C/D → change Mode/Gain/Threshold → return A/B` remains
  non-exportable until the current cached A/B presentation actually settles; after
  settlement the semantic filename and PNG bytes must describe the same preview;
- a cached Difference numerical map is insufficient to make export active and export
  never invokes Calculate merely to satisfy its own availability;
- configured Export directory and last-directory behavior are reused without a new
  Settings schema; default analysis filenames include millisecond-resolution export
  timestamps and user-edited filenames remain respected;
- Cancel/no path and write failure leave the workspace unchanged and provide only
  compact feedback on failure;
- successful export leaves Selected, Active, Primary, Current Comparison Page,
  source generation, Difference cache identity/content, normal source workers,
  preload ownership, and residency semantics unchanged;
- Difference PNG encoding/file I/O uses the existing bounded analysis worker pool
  and introduces no new pool; CSV serialization uses already-computed in-memory
  series;
- production composition installs one stable set of export actions and local table
  controls across repeated composition; teardown disarms late table callbacks; and
- closing/recreating MainWindow while a Difference PNG worker is physically running
  cannot let late completion mutate deleted UI.

Run the focused P4-E suite before the standard repository contract:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\unit\test_analysis_export.py `
    tests\unit\test_analysis_export_metrics.py `
    tests\ui\test_p4e_analysis_export.py `
    tests\ui\test_p4e_analysis_productivity.py `
    tests\ui\test_p4e_analysis_export_lifecycle.py `
    tests\ui\test_p4e_analysis_export_review_regressions.py
```

The repository owner reports this requested focused validation and the requested
post-fix static checks PASS on code/test head
`d8fa4b0c0ffe0a3517d37c703c490ec399f8ccf9`. The reported static checks include
`mypy src`, Ruff check, Ruff format check, and `git diff --check`. Any later
merge-closure documentation commit is docs-only and does not extend that observed
runtime/test PASS claim to unrun commands.

Agent-side validation may record only commands actually observed. Owner/local
Windows PySide6 validation remains authoritative when the agent environment does not
contain the pinned Qt runtime.

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

## P5-A deterministic Remote IQA result contract — historical schema v1

`tests/unit/test_remote_iqa_v1.py` generates and consumes an 11-Scene production-
shaped schema-v1 result without network, GPU, or Qt UI. It verifies all ten
attributes, two-source and 3-source identity, dynamic grids, optional detail, exact
epsilon/A-B/quality/bias orientation, W/S1/S2/count/valid recomposition, pairwise
intersections, both official aggregation modes, invalid results, non-integer affine
geometry, and publication/artifact safety.

The Tier-1 fixture oracle is independent from production recomposition, with separate
hand-calculated exact golden assertions. Review regressions also cover zero-epsilon
undefined ratios, negative/non-finite power, neutral quality, inconsistent moments,
general affine polygon clipping across every source boundary, required comparison
operators, analysis-bounded valid rectangles, official-mode applicability, and
adversarial archive/member metadata.

Safety coverage includes incomplete publication, dimension mismatch, missing and
corrupt compact data, traversal/absolute/NUL/symlink escape, object arrays, malformed
dtype/rank/shape, and declared/actual safety-ceiling rejection before unrestricted
NumPy allocation or decompression. The historical focused command is:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_remote_iqa_v1.py tests\unit\test_remote.py
```

Schema v1 remains read-only compatibility after P5-A2; its historical aggregation
behavior is not silently changed to match v2.

## P5-A2 Stage 2 deterministic executable-v2 contract

PR #40 must be validated as the executable schema-v2 authority, not only as a parser
round-trip. The focused files are:

```text
tests/unit/test_remote_iqa_v2.py
tests/unit/test_remote_iqa_v2_limits.py
tests/unit/test_remote_iqa_v2_review_regressions.py
```

The v2 golden/safety matrix must establish at minimum:

- canonical dispatch: real schema-v1 golden remains read-only while schema-v2 uses
  the native v2 reader and future versions are unsupported;
- deterministic N-way `variant_id`/source/context identity and exact variant order;
- repeated `source_id` acceptance within/across Scenes only when immutable concrete
  metadata matches, including an identical-source multi-variant zero-delta sanity case;
- deterministic `measurement_context_id` and tamper rejection;
- canonical Scene `ΣS1/ΣW`, pooled Dataset, and equal-Scene Dataset statistics using
  hand-calculated cases that distinguish the reductions;
- Mode 1 ratio-of-weighted-means and Mode 2 unweighted mean of **finite** per-grid
  log-ratios, including a mixed `0/0` + finite-cell case and a no-finite-ratio case;
- reference reversal, signed target-minus-reference, and centralized higher/lower/
  neutral quality orientation;
- pair-valid support, negative/non-finite/zero power, epsilon behavior, inconsistent
  moments, and projection-tolerance corruption;
- COMPLETE cardinality, exact cross-variant geometry/grid correspondence, and no
  client alignment/imputation;
- summary-first open proving Scene grid/detail files are not touched until the
  explicit grid-load boundary;
- POSIX/Windows path traversal/absolute/UNC rejection and deferred containment;
- malformed, duplicate, encrypted, unsupported-compression, object/pickle,
  wrong-dtype/rank/shape, declared-size and bounded archive/member/array failures;
- explicit parser ceilings for variants, Scenes, attributes, aggregate source
  bindings, grid cells, detail references, manifest, summary, Scene artifact,
  archive, member, and ndarray size;
- v2 PARTIAL remaining `UNSUPPORTED` until P5-C freezes its detailed shape.

The aggregate `1024` source-binding ceiling is an acceptance safety envelope rather
than a cache budget. Its merge rationale is Stage-1's approximately 300-source
production planning assumption with >3x headroom; future larger requirements require
explicit schema/safety review.

Run the focused compatibility/v2 suite before the standard repository contract:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\unit\test_remote_iqa_v1.py `
    tests\unit\test_remote_iqa_v2.py `
    tests\unit\test_remote_iqa_v2_limits.py `
    tests\unit\test_remote_iqa_v2_review_regressions.py `
    tests\unit\test_remote.py
```

Because PR #40 changes `src/`, `tests/`, and durable docs, the full Standard
validation matrix at the top of this document and the broader applicable pytest
regression suite remain required before merge. A reduced/pre-review harness result
must not be promoted into a latest-head PASS claim. At the time this Stage-2 quality
contract was written, repository-pinned latest-head pytest/Ruff/mypy/docs/pip/diff
validation had not yet been observed.

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
