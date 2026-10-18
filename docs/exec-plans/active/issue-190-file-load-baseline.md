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
