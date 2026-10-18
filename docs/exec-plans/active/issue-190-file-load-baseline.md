# Issue #190 diagnostic baseline

Status: Draft experiment; independent methodology review pending.
Owner: ChatGPT-assisted, under explicit owner authorization.
Links: [#190](https://github.com/delphykmc/pixelscope/issues/190),
[#189](https://github.com/delphykmc/pixelscope/issues/189).
Base: `a9ecbf49757b0135e658cc9842722b1604c3f2f1`.

## Scope and provenance

One experiment branch and one Draft PR. No optimization, shipping behavior,
merge, release, dependencies or CI changes. Normal automatic GC stays enabled.
Earlier conversation reported a local runner/commit and 19 passing tests, but
that branch, commit and runner are absent from this Windows repository and the
connected GitHub repository. That earlier result is not reproduced evidence.
The runner here is reconstructed against the pinned public MAIN composition.
Synced project references and the owner's existing checkout are unchanged.

## Method

`scripts/issue190_baseline.py` creates separate watchdog-bounded children for
every case/warm-up/repetition. Fixtures and QSettings are isolated before timing.
Defaults: 2 warm-ups plus 8 exploratory samples; rotate case order by repeat.
The parent preserves failure/timeout samples and never replaces them by retries.
Run in isolation; do not run tests or other measurement suites simultaneously.

```powershell
$env:PYTHONPATH = "$PWD/src"
$env:QT_QPA_PLATFORM = 'offscreen'
python scripts/issue190_baseline.py --output temp/issue190-run --warmups 2 --repeats 8
```

Use the repository's CPython 3.10 x64 environment. `--lanes E2,E3` selects cheap
lanes; `--warmups 0 --repeats 1` is smoke only. Use a new output directory per run.
Remove the Qt platform override for a native Windows follow-up; even native Qt
paint completion does not establish physical monitor scanout.

- E2: actual composed Open replacement then Quick Compare Drop addition, with
  injected worker discovery and a GUI timer releasing a 750ms test-owned barrier.
  Folder fixture: 128 unique supported PNGs and 128 unsupported text files.
  Record enqueue/discovery/row insertion milestones, FIFO, final A/B intent,
  folder completion/natural order/no auto-select, unique IDs and stale count.
  This measures registration, not decode or presentation. The folder's actual
  local discovery cost is included separately from the synthetic barrier.
- E3: 1/100/1000 resident 8x12 grayscale documents, no large decoded buffers.
  L1 handler wall-time has no model observers; L2 separately counts Qt
  dataChanged and selectionChanged proxies. Programmatic select, mouse select,
  keyboard navigation, Primary focus and state refresh are exercised. Signal
  counts are not exact setter counts. Checks sit outside each handler timer.
- E1: fresh two-UHD-RGB8 Open/Drop, B reader delayed 0/250/1000ms on its worker.
  Existing QSignalSpy first-frame signals and GUI readiness polling provide
  partial observations. Pixel equality is checked after the measured wait.
  Worker read return is not GUI acceptance; GUI polling timestamps are upper
  bounds and include event-loop observation latency.

## Bounded E1 stop and missing evidence

E1 exact attribution is **INCONCLUSIVE**. Existing signals lack request epoch,
view revision and post-reuse logical-slot binding; polling cannot repair that.
No new production observer is added: a three-seam implementation would need a
separate diagnostic commit plus OFF/ON parity, reuse, spinner, reopen, pan/ROI,
fit=False and normal-GC lifecycle prevalidation before exact claims are valid.
The cheap lanes are delivered without pretending these prerequisites passed.
Qt reviewer: determine whether that narrow follow-up is justified.

G3 is unavailable: no representative accessible UNC was supplied. No scheduler
recommendation follows from G1 synthetic FIFO delay. U1-U4 remain inconclusive
as optimization hypotheses; this runner has no candidate or pre-registered MDE.
Peak process memory, viewport repaint counts, tagged-folder/theme metadata and
broader interaction parity rely on separate coverage/review, not on timing samples.
No three independent reviews or chair adjudication are claimed.

## Output and validation

Ignored `temp/<run>/` contains run_meta.json, cases.jsonl, summary.json,
decisions.json and per-child result/stdout/stderr. Logs may contain local paths;
do not publish raw logs. Summaries contain no paths or pixels. E1 signals contain
random document IDs, not reusable slot identities. Eight samples establish no
precise tails or improvement. All timing conclusions remain provisional until
Qt/System reviewers validate methodology.

Validation/result records will be appended after the final run. The initial smoke
exposed a harness relative-vs-canonical-path comparison error; that failed run is
retained locally and is not reported as a passing measurement. No production
assertion or correctness gate was relaxed.

Agent commits carry `Co-authored-by: ChatGPT <noreply@openai.com>`; GitHub activity
uses the connected owner account and explicitly says ChatGPT-assisted. Existing
human commits are not rewritten. This plan and runner are experiment artifacts;
retain/close-unmerged disposition remains with review and the chair.

## Observed Windows offscreen results — 2026-10-19 KST

Final run: `temp/issue190-final`. **140/140 child executions passed**, including
28 warm-ups; 112 exploratory observations, eight per condition. No failed sample,
timeout, crash, retry or replacement. Every child asserted normal automatic GC.
These are provisional G1 measurements pending independent methodology review.

Measured local source commit: `de2ac78fcaa9350009d897efcf6cfb0e1d981843`.
Published source commit: `790253f3b73ba287d3c23234b8bab900e07d84d8`.
Their complete Git trees are identical: `1a205d9658782e012df8d717dd17d63484084d54`.
The different commit IDs reflect connected-tool publication after local Git push
failed to initialize network access. No existing human commit was rewritten.
Later report-only commits do not change measured source.

Windows build 26200, CPython 3.10.11 x64, PySide6 6.4.2, NumPy 1.24.4,
OpenCV 4.8.1, pyqtgraph 0.13.7; Qt offscreen in the restricted execution
environment. Generated files and OS filesystem caches are warm/uncontrolled.
Native interactive UI and representative SMB acceptance were not performed.
E1 enables the existing single-target load trace; its logging overhead is not
calibrated, so E1 numbers are partial observations only, not precise paint costs.

### E2: registration, milliseconds

| Case | A enqueue to discovery | A enqueue to row | B enqueue to discovery | B enqueue to row |
| --- | ---: | ---: | ---: | ---: |
| Control median | 2.11 | 18.80 | 32.62 | 57.12 |
| Contended median | 7391.79 | 7397.83 | 7414.87 | 7429.60 |

A enqueue-to-discovery raw samples, run suffixes `02` through `09`:

- Control: 2.4890, 2.1425, 2.1736, 2.0733, 3.4245, 2.0407, 2.0410, 1.9904.
- Contended: 6846.0591, 7098.5748, 7450.4153, 7333.1581, 6947.1429,
  8076.8126, 7793.0257, 8037.3185.

This reproduces FIFO head-of-line delay in the specified synthetic scenario.
The contended duration includes both the configured 750ms causal barrier and
actual restricted-local discovery/registration cost for 256 directory entries.
It is **not** a 750ms network emulation or an SMB speedup estimate. Discovery
start marks the injected worker wrapper entering, before its barrier; this
version has no independent barrier-release timestamp. Heartbeat max-gap medians
were 41.79ms control and 29.09ms contended; these do not establish a relative UI
responsiveness improvement because workload and observation windows differ.
All FIFO, final A/B order, folder eventual completion/natural order/no auto-select,
unique-row and registration stale-count assertions passed.

### E3 L1: synchronous handler wall-time, milliseconds

| Resident documents | Select one | Keyboard Down | Mouse select | Primary focus | Update states | Max heartbeat gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 4.98 | 0.32 | 0.16 | 3.91 | 0.06 | 16.13 |
| 100 | 7.22 | 7.08 | 6.90 | 9.95 | 1.46 | 20.75 |
| 1000 | 22.86 | 22.09 | 21.75 | 38.22 | 14.45 | 48.88 |

Raw `_update_file_states` samples, run suffixes `02` through `09`:

- 1: 0.0975, 0.1464, 0.0466, 0.0496, 0.0723, 0.0702, 0.0531, 0.0489.
- 100: 1.4896, 1.4639, 1.4341, 1.6314, 1.4602, 1.4651, 1.8622, 1.4036.
- 1000: 14.6562, 14.3313, 14.3762, 13.8966, 15.2409, 15.0021, 13.6408, 14.5300.

Separate L2 runs emitted aggregate dataChanged/selectionChanged counts of
4/4, 825/7, and 8025/7 for 1/100/1000 documents, identical across all eight
samples at each size. These aggregate counts also include between-action setup
and event processing. They are Qt model proxies, not exact setter counts or
viewport repaint counts. L2 timings are retained separately and not pooled into
L1. No 10k case was run. Current-item/order, active metadata/tooltip, mouse,
keyboard and scrollbar assertions passed. Catalog-size-dependent work is observed;
no F4 candidate, effect size or pre-registered MDE was tested.

### E1 partial lane

| B worker delay ms | Open readiness + partial signal median ms | Drop readiness + partial signal median ms |
| --- | ---: | ---: |
| 0 | 184.59 | 269.72 |
| 250 | 410.94 | 485.62 |
| 1000 | 1173.77 | 1241.92 |

Both sources retained exact expected UHD RGB8 values in all samples. The wait
ends after GUI polling sees both resident sources, at least one existing
first-frame signal and no foreground worker. It does not require valid paint
attribution for every occupied slot. GUI polling timestamps and captured signals
remain observational upper bounds; worker reader return is recorded separately.
Do not use this table as a precise Open-versus-Drop comparison or first-tile
latency claim. **E1 exact attribution remains INCONCLUSIVE.** No observer seam,
OFF/ON parity, same-preview, epoch, reuse, spinner-only or pan/ROI oracle was
implemented or declared passed. Qt review should determine the next narrow slice.

### Validation commands and exact outcomes

All commands use the pinned environment with `PYTHONPATH=src` and offscreen Qt.

```powershell
python -m pytest -q tests/unit/test_issue190_summary.py tests/ui/test_large_folder_registration_performance.py tests/ui/test_large_folder_registration_composition.py tests/ui/test_open_images_registration.py tests/ui/test_preload_promotion.py tests/ui/test_large_folder_registration_lifecycle_review.py tests/ui/test_files_drag_selection_debounce.py tests/ui/test_preview_passthrough.py
# 37 passed in 17.46s
python scripts/issue190_baseline.py --output temp/issue190-final --warmups 2 --repeats 8
# 140 child executions ok; exit 0; failures=[]
python -m pytest -q -o usefixtures=isolated_qsettings tests/ui/test_primary_style_work.py tests/ui/test_file_status_icons.py tests/ui/test_design_tokens_style.py tests/ui/test_large_folder_registration.py tests/ui/test_multiview_gain_diff_stability.py
# 21 passed in 9.58s
python -m pytest -q tests/unit/test_issue190_summary.py tests/unit/test_qt_lifecycle_architecture.py tests/unit/test_architecture_boundaries.py
# 7 passed in 0.40s (summary test intentionally repeated after metadata changes)
python -m ruff check .
python -m ruff format --check .
# Passed; 350 files already formatted
python -m mypy src
# Success: no issues found in 108 source files
python scripts/check_docs.py
# Documentation contract passed (rerun after this report update)
python -m pip check
# No broken requirements found
git diff --check
# Passed
```

Full repository pytest was not run; no repository-wide clean or merge-ready
claim is made. Existing composed tag behavior, RAW sidecar and lifecycle tests
passed within the focused selections. Dedicated dynamic theme-invalidation
oracle, real SMB, process peak-memory and physical display acceptance remain
unverified. No correctness assertion was weakened, no GC suppression was used,
and no CI suite was expanded.

### Reproducibility and next review

Raw metadata/samples/summary/decisions are retained locally under ignored
`temp/issue190-final/`; each case has `00`/`01` warm-ups and `02`–`09` samples.
Per-child logs and fixtures are also there. Re-run from the published measured
source commit using a fresh output directory; log files can contain local paths
and are intentionally not committed. This report contains anonymized aggregate
and selected raw distributions, not personal paths or pixels.

- Runner SHA256: `ff9c759205c73894fd10073d8b6fb811f0d9cc6842526b506fbc64181f175190`.
- cases.jsonl SHA256: `320e7bd72a702e489e76be17c950979d8aa6677776c20d7b9d24c61af4cd1ada`.
- summary.json SHA256: `008bfd7b5261e237d83887d144c4f5aa187f6a16327031f582bda10482409951`.

Qt/System/QA independent methodology/results reviews are still pending. U1–U4
optimization hypotheses remain inconclusive; G1 observations do not endorse a
priority scheduler, residency policy or Files optimization. G3 unavailable.
The chair's MDE/adjudication and return to #189 are later steps, not completed
by opening this Draft PR. Keep #189/#190 open and PR #191 Draft and unmerged.

## Round-4 follow-up plan and reporting correction

P0.1 corrects the prior report's swapped U2/U3 machine output: U1=F1 first tile,
U2=S4 old-pair/placeholder, U3=S7 FIFO/HOL, U4=F4 Files. The old raw run and hashes
above remain immutable. This is a post-processing/reconciliation correction of
published report `d4f9004dd47927d812da58956f571cce1f3c6fc9` and measured source
`790253f3b73ba287d3c23234b8bab900e07d84d8`, not a change to observed samples.
Schema v2 exposes IDs, hypotheses, cases/run IDs, result enum, evidence grade,
reason and limitation; G1 mechanism evidence is separate from optimization.
Regression tests lock the mapping and reject failed/warm-up-only support.

E3 callback wall-time stops before the following app.processEvents(). New L2
per-action snapshots separate synchronous signals from subsequent event processing;
aggregate counts include setup and remain neither setter counts nor painted frames.

P0.2: separate E2 barrier enter/release, actual discovery, GUI row span and
registration-finished/handoff; add 0ms and small-folder comparators.
P0.3: check real desktop presentation before assigning native G2; replay Files
1/100/1000 and an independent resident two-UHD Primary/Diff lane. Otherwise report
G2_unavailable with exact owner commands. No shipping/optimization changes.
P1: E1 stays INCONCLUSIVE during P0. A separate Qt-reviewed three-seam commit
and OFF/ON/lifecycle prevalidation would be needed before believing exact identity.

## Round-4 observed follow-up results — 2026-10-19 KST

P0.1 reporting correction is published at
`76b9104a1c335075a26ef73fb8cd07ed1ff0731b`. The measured follow-up source is
`7d5e64a407b2916aca26683b4a7d26a66949cdf5`; local measured source
`8167cffdab11496219676b3907a76368fb2d59b8` has the same complete tree
`1cf5f3d4e47be4317a30bb77c5983dc9be461f9f`. Both run metadata records report a
clean tree. Subsequent export/test/report additions do not alter measured code.

The [anonymized machine-readable evidence](../../experiments/issue-190-round4-evidence.json)
contains all new scalar samples, summaries, per-action proxies, corrected decisions,
run IDs, metadata and original-file hashes. It also supplies a **reconciled copy**
of the original run's decisions, with U2=S4 and U3=S7. Historical raw samples,
statistics and the erroneous historical decisions file remain untouched; consumers
should use the reconciled schema-v2 output, not the old flat U2/U3 sentences.
All optimization results remain `inconclusive`; only the specified G1 FIFO
mechanism has a separate supported flag. Control-only, warm-up-only and failed
evidence cannot establish that mechanism flag.

Final matrices: **E2 40/40 passed**, **native E3/E3K 100/100 passed**, total
140/140, including 28 warm-ups and 112 observations. Each condition has two
warm-ups and eight samples; there were no failed final samples, timeouts, crashes
or retry substitutions. Normal automatic GC is asserted in every child. These
are independent fresh child processes, with no concurrent agent test suite.
OS caches are uncontrolled; fixtures are generated before timing and are warm.

### P0.2: causal decomposition, G1 only

Median milliseconds, n=8. Each timeline records barrier enter/release, actual
worker discovery start/return, GUI first/last row insertion, idle-progress
registration-finished, and A/B enqueue/discovery/registration. The commit marker
is emitted on the GUI thread after active registration state clears and before
the next request starts; it is not a physical-paint marker.

| Case | Actual barrier wait | Actual discovery work | GUI row span | Discovery return to registration commit | Commit to A dispatch | A queue wait |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No-folder control | — | — | — | — | — | 2.06 |
| 128 PNG + 128 unsupported, 750ms config | 750.10 | 7155.27 | 36.23 | 67.56 | 1.61 | 7974.08 |
| Same folder size, 0ms config | 16.44 | 7279.92 | 39.95 | 76.03 | 2.60 | 7371.51 |
| 8 PNG + 8 unsupported, 0ms config | 15.55 | 501.90 | 2.96 | 42.03 | 5.13 | 568.83 |

Zero configuration is not zero observed wait: queueing A/B and delivering the
GUI timer still take time. Timer granularity also permits configured 750ms to
vary; actual release timestamps, not requested durations, are used. The export
additionally includes release-to-worker-resume, worker-return-to-first-row,
last-row-to-commit and both direct registration times. Row span includes GUI
scheduling/yields, not just CPU setter cost; return-to-commit includes GUI
handoff, registration and folder completion/history work. Component medians must
not be summed as if they described the same raw run.

The long restricted-local discovery interval dominates this synthetic FIFO
scenario; the 750ms barrier is only one component. Original 7391.79ms versus new
7974.08ms is a different diagnostic run, **not candidate performance comparison**.
No real SMB workload was measured and no preemptible scheduler checkpoint or
priority policy is established. FIFO/order, exact final [A,B], folder eventual
completion/natural order/unique IDs/no auto-select and stale-count gates passed.

### P0.3: native Windows execution and its verification limit

The run used actual Qt **windows** QPA, not offscreen. All 100 native samples
recorded visible/exposed, non-minimized windows on a 3440x1440 screen, DPR 1.0.
Windows Computer Use independently listed the actual source diagnostic window
`PixelScope #190 diagnostic E3_L1_1000`. However, external activation/capture
returned **Computer Use app approval timed out**. The screenshot proof gate
therefore timed out and no external screenshot was obtained.

Consequently **G2_unavailable**: native programmatic measurements below remain
G1 diagnostics with unverified on-screen visual acceptance. Merely Windows QPA,
isVisible/isExposed, window enumeration or processEvents return does not establish
user-visible latency, final Qt frame identity or physical scanout. No native G2
claim or human manual acceptance is fabricated.

#### Catalog-only native diagnostic

Median synchronous callback wall-time in milliseconds. The timer stops **before**
the subsequent app.processEvents(); no per-row/model spies are installed in L1.
These are 8x12 grayscale resident documents, independent of the two-UHD lane.

| Documents | Select one | Keyboard Down | Mouse select | Primary focus | Update states |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 4.81 | 0.32 | 0.18 | 3.91 | 0.06 |
| 100 | 7.11 | 6.96 | 6.92 | 9.67 | 1.45 |
| 1000 | 22.66 | 21.67 | 21.77 | 37.69 | 14.15 |

Separate L2 per-action **dataChanged** deltas, identical across eight samples:

| Documents | Select one | Keyboard | Mouse | Primary | State update |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 0 | 0 | 1 | 1 |
| 100 | 106 | 106 | 106 | 206 | 100 |
| 1000 | 1006 | 1006 | 1006 | 2006 | 1000 |

selectionChanged deltas are 2 for select-one; keyboard/mouse are 1 at 100/1000
and 0 at 1; Primary/state update are 0. Subsequent-event model-signal deltas
were zero for these actions. Aggregate counters still include between-action
setup and must not be assigned to one action. These are model signal proxies,
**neither exact Qt setter counts nor painted frames**. Disabled L1 model counters
are omitted from the safe export and marked model_proxy_enabled=false.

#### Independent two-UHD resident diagnostic

Exactly two 3840x2160 RGB8 sources, generated values A=17/B=93, already resident;
Difference cache computed before timing. No source paths, decode, network or
Recent-history cost is part of this lane. Each action records handler return,
one subsequent processEvents return and a separate bounded idle observation.

| L1 Diff state | A to B sync | A to B next events | B to A sync | B to A next events | Diff visibility toggle sync | Files-only state sync |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OFF | 7.67 | 8.20 | 7.78 | 8.49 | 8.27 (OFF) | 0.09 |
| ON | 9.13 | 12.29 | 8.51 | 9.59 | 10.29 (ON) | 0.10 |

All values are medians in milliseconds, n=8. The idle observations are in the
JSON; they are not additional wall-time to add to next-events (they share the
same handler-return origin). These observations do not guarantee that every
viewport finished painting. L2 stays independent: dataChanged=10 for each Primary
direction, 4 for cached Diff visibility and 2 for Files-only state update;
selectionChanged=0 and subsequent-event model deltas=0, in all eight samples.

Correctness: identical source/preview references, generations and pixels;
unchanged load tokens, zero foreground load dispatch, same ordered selection,
proper Primary document/first occupied viewer, expected 2/3 occupied tiles,
stable Difference source/cache/pixels and correct visibility. A separate focused
two-case UHD UI test verifies source and Difference A/B header metadata under
both OFF/ON. Binding/view-range snapshots are taken outside timing and retained
locally; they show effective identity/range only. No exact timed viewer/rebind/fit
or aux/Diff attribution is guessed without an observer. This low-N resident
baseline cannot assign the owner's file/network two-4K delay to F4.

### Validation and evidence publication

```powershell
$env:PYTHONPATH = "$PWD/src"
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest -q tests/unit/test_issue190_summary.py tests/ui/test_large_folder_registration_performance.py tests/ui/test_large_folder_registration_composition.py tests/ui/test_open_images_registration.py tests/ui/test_preload_promotion.py tests/ui/test_large_folder_registration_lifecycle_review.py tests/ui/test_files_drag_selection_debounce.py tests/ui/test_preview_passthrough.py tests/ui/test_primary_style_work.py tests/ui/test_file_status_icons.py tests/ui/test_design_tokens_style.py tests/ui/test_multiview_gain_diff_stability.py
# 55 passed in 21.24s
python scripts/issue190_baseline.py --output temp/issue190-r4-e2 --lanes E2 --warmups 2 --repeats 8
# 40/40 ok, exit 0
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
python scripts/issue190_baseline.py --output temp/issue190-r4-native --lanes E3,E3K --warmups 2 --repeats 8
# 100/100 ok, exit 0; windows QPA, external visual validation unavailable
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest -q tests/unit/test_issue190_summary.py tests/unit/test_issue190_evidence.py tests/ui/test_issue190_followup.py
# 10 passed in 3.74s
python -m ruff check .
python -m ruff format --check .
# Passed; 354 files already formatted
python -m mypy src
# Success: no issues found in 108 source files
python scripts/check_docs.py
# Documentation contract passed; rerun after this report edit
python -m pip check
# No broken requirements found
git diff --check
# Passed
```

No lifecycle/Traceback/RuntimeError patterns were found in the final matrices'
captured logs. Development attempts remain preserved: five pre-freeze smoke
children failed on the helper import path and were fixed before measurement;
the external native-proof gate timed out without release. These are explicitly
separate from the two final matrices, not silently replaced passing samples.
Full pytest, real SMB, peak residency, dynamic theme invalidation and human
native/physical display acceptance remain unverified. Existing tag/style/RAW
and shutdown coverage passed within the focused slice; no gate was weakened.

Safe evidence SHA256:
`f3c329f8f65f75238dc6c2ed1c8b21b63384b6cfcd021d06153ac95cc3c482f7`.
`scripts/issue190_evidence.py` allowlists scalar records and removes error text,
paths, binding addresses/UUIDs, source payloads, settings and logs; its privacy
regressions passed. The JSON carries all sample values and new raw-file hashes.
Original raw hashes above were rechecked unchanged. Local complete raw output
remains ignored under temp/; only the anonymized evidence export is published.

For an owner-visible rerun, use the exact native command above with a **fresh**
output directory such as temp/issue190-r4-owner-native, observe/capture the actual
window and record desktop/visibility evidence separately before assigning G2.
The optional child-only --proof-wait flag pauses untimed setup until continue.json
appears in that child's output directory (55-second cap); no proof release was
fabricated in this session.

P0.1/P0.2 delivered; P0.3 native diagnostic delivered with G2 visual acceptance
unavailable. **P1/E1 remains INCONCLUSIVE and deferred**: no three-seam production
observer, OFF/ON overhead or observer lifecycle validation was added or claimed.
Qt/System/QA should now review the corrected IDs, decomposed timeline, native
evidence grade and separate low-N UHD attribution limits. Stop here for result
reviews and chair adjudication; no performance candidate, merge or extra PR.
