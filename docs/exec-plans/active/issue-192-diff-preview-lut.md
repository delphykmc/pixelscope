# Issue #192: C1 byte-exact Difference preview LUT

Status: Complete implementation/verification, independent review pending; not merged.
Owner: ChatGPT-assisted. Branch: perf/issue-192-c1-diff-preview.
Baseline/main independently verified: a9ecbf49757b0135e658cc9842722b1604c3f2f1.
Issue: [#192](https://github.com/delphykmc/pixelscope/issues/192).
Historical diagnostic [#191](https://github.com/delphykmc/pixelscope/pull/191)
remains separate, Draft and unmerged. No C2, async lifecycle, queue or eager prewarm.

## Contract and design

Only render_absolute_difference's genuine uint8 image path is specialized.
Actual-map maximum, float32 multiply/divide order, clipping and ties-to-even
rounding remain unchanged. Evaluate those codes on 256 entries, then apply the
byte table with existing OpenCV LUT (no dependency added). New C-contiguous
uint8 output, no input mutation, no global table or retained state. Non-byte,
array-subclass/non-image shape, extreme/non-scalar gains and other renderer
functions keep original arithmetic. Bounds 1e-30..1e30 ensure unused LUT codes
cannot introduce overflow/underflow/invalid errors absent from the actual map;
extreme valid gains retain the baseline's exact result/error behavior.

Before any product edit: an independent main-function snapshot and exhaustive
actual maxima 0..255 tests passed. The first naive LUT exposed strict-error
infinite-gain behavior, corrected via fallback rather than weakening equality.
Initial NumPy gather measured ~22ms Gray/~67ms RGB versus ~60/~185ms baseline.
Existing OpenCV LUT mapping measured ~2.3ms Gray/~5.6-7.5ms RGB; byte goldens
passed before promotion. Full raw isolated microbench will accompany results.
All micro cases use 3840x2160, maxima 0/127/255, gains 1/1.25, stable buffers,
normal GC, 2 warm-ups +8 observations, interleaved order and exact pixel checks.

## Pre-registered user-path study (before A/A and A/B)

One RGB8 first-preview-MISS condition. Reuse the two seeded textured on-disk UHD
fixtures from D1; actual composed Open A/Quick Compare B disk loading, passive
map+metrics HIT, hidden Diff and no pre-render. Cold first ON, untimed OFF, warm
re-ON, then independent same-key getter probe. Test-owned class-native hooks
capture actual curation callback, getter/preview MISS/HIT, numerical renderer,
store/render, GUI thread, map/preview state, heartbeat and process memory. No
Qt instance-method wrapper, forced paint, GC disabling or production UI changes.
Source/preview/map/derived pixels, same pair/generation/ROI/controls/key, stale
counters, array ownership, five extra toggles and close/drain are hard gates.
Geometry snapshots record center, ViewBox pixel scale and dimensions separately;
no raw-viewRange or internal qimage pointer gate is substituted for presentation.
Foreground A/B readiness is a worker/registration/GUI polling upper bound, not
completed paint. Exact current-slot/Diff paint and scanout stay INCONCLUSIVE.

1. A/A: two labels both unmodified pinned main, alternate order per block;
   2 warm-ups +8 observed fresh-process pairs (20 children).
2. Compute and publish calibration BEFORE A/B. Action noise bound is maximum
   absolute paired A/A first-ON delta. MDE = max(50ms, 3 * action noise bound).
   Foreground A/B and memory noise bounds are their maximum absolute paired
   A/A deltas. A/A medians/drift and raw vectors must be reported, no replacement.
3. Screening: baseline/candidate, interleaved/reversed per block, 2 warm-ups +8
   observations/version. Require median first-ON reduction >= MDE and >=50ms.
   Strong target: candidate median <=60ms and reduction >=100ms, warm median
   <=30ms; foreground median regression no larger than measured A/A noise.
4. Only if screening passes, confirmation: 2 warm-ups +20 fresh observations
   per version, interleaved. Same thresholds and all correctness gates; no p95
   or automatic merge. Memory/foreground regressions must be explained or vetoed.

Any mismatch or stale/lifetime/ownership failure blocks acceptance. No failed
sample replacement, no silent scope expansion. Native Windows CPython 3.10,
normal GC and OS cache warm/uncontrolled. Memory snapshots include validation
buffers; lifetime peak working set is not action allocation or peak private.
Observer overhead uncalibrated but identical across versions. Same driver and
fixture hashes, source commit and source-file hash recorded per version/run.
Full local pytest only if owner chooses; applicable focused unit/UI and broad
static/docs gates required. Feature PR remains review-only until owner decision.

## Reproduction

scripts/issue192_benchmark.py accepts --phase AA/screening/confirmation, --baseline,
--candidate, --fixtures and a fresh --output. It runs each child with only its
chosen source checkout first on sys.path and verifies imported source ownership.
Logs/fixtures remain ignored; published scalar evidence excludes local paths.
Commands, calibrated MDE, source/fixture/raw hashes and final results follow.

Git/GitHub activity is explicitly ChatGPT-assisted; commits have coauthor trailer.

## Frozen source and calibration

Separate review-only [PR #193](https://github.com/delphykmc/pixelscope/pull/193).
Measured candidate local `b3580631ee81527616bd6a2cf91303737316f212`, published
`140d20110aebee6339a55e5dc7e55882bf400985`; identical complete source tree
`c7249611bf56d1ed7b71a5d7b84e8ba540bd90b4`. The production diff is confined
to render_absolute_difference. Existing OpenCV is used without new dependencies,
thread settings or process-global state. Supplemental tests/reports do not
change this measured function/driver. Main remains the pinned a9ecbf4 baseline.

Before A/B, A/A **20/20 children passed**. Observed first-ON medians A0/A1:
210.48215 / 210.18910ms; max paired absolute delta 13.373ms. Registered MDE:
max(50, 3*13.373) = **50ms**. Foreground A/B noise limits 59.8185/38.1514ms.
Cold RSS/private/lifetime-peak-RSS snapshot-delta bounds: 606208/638976/122880
bytes. [Registration was posted before screening](https://github.com/delphykmc/pixelscope/issues/192#issuecomment-6264207963)
at 2026-10-19T09:36:46.762890Z; raw A/A vectors remain in the evidence.

## Screening result, n=8 observed/version

All 20 attempted children passed, including four warm-ups. Eight observed
baseline/candidate pairs, alternating execution order; no replacement/retry.

| Median metric | Baseline | C1 |
| --- | ---: | ---: |
| First ON QAction trigger-return ms | 212.115 | 32.172 |
| Absolute renderer ms | 186.346 | 6.311 |
| Re-ON ms | 20.156 | 20.309 |
| First post-action heartbeat gap ms | 216.983 | 36.486 |
| Foreground A readiness upper bound ms | 633.649 | 628.542 |
| Foreground B readiness upper bound ms | 286.523 | 280.804 |
| Cold RSS delta bytes | 26345472 | 26415104 |
| Cold private delta bytes | 26099712 | 26099712 |
| Lifetime peak RSS counter delta bytes | 174770176 | 0 |

First ON reduction 179.943ms exceeds the registered 50ms MDE; strong callback
targets also pass. Foreground medians do not regress beyond A/A noise; RSS
delta increase is below measured noise, private delta unchanged, lifetime peak
delta lower. Inclusive nested timers overlap; never sum their medians. Peak
working set is a process-lifetime counter, not action allocation or peak private.

Numerical map/metrics HIT, first preview MISS, subsequent document reuse and
separate same-key getter HIT were checked in every valid child. The production
selected absolute payload is uint8. Exact source/map/preview bytes, independence,
pair/order/generation/ROI/controls/key, no stale publish, normal GC and five extra
toggle cycles passed. Same source-view center/pixel-scale snapshots were
recorded across the default fit transition; these are not a paint oracle.
The initial source geometry may still be a pre-fit state. Do not turn the
geometry or foreground readiness snapshots into valid-paint claims.

The [screening result](https://github.com/delphykmc/pixelscope/issues/192#issuecomment-6264278421)
was posted before proceeding to the prescribed 20-observation/version confirmation.

## Confirmation result, n=20 observed/version

All 44 confirmation children passed, including four warm-ups. Combined matrices
are **84/84 attempted children passing**: A/A 20, screening 20, confirmation 44;
12 warm-ups and 72 observed records. No failed case replacement, retry or source
change within the matrices. Each phase used the same frozen driver hash below.

| Confirmation median | Baseline | C1 |
| --- | ---: | ---: |
| First ON QAction trigger-return ms | 211.047 | 32.141 |
| Absolute renderer ms | 184.697 | 6.292 |
| Re-ON ms | 20.196 | 20.182 |
| Post-action heartbeat gap ms | 215.795 | 37.469 |
| Foreground A readiness upper bound ms | 631.958 | 628.480 |
| Foreground B readiness upper bound ms | 281.840 | 286.966 |
| Cold RSS delta bytes | 26359808 | 26435584 |
| Cold private delta bytes | 26099712 | 26118144 |
| Lifetime peak RSS counter delta bytes | 174749696 | 0 |

Difference of first-ON medians: **178.906ms**. Median blocked/paired reduction:
**178.801ms**, range 173.724-193.704ms (all twenty raw deltas in evidence).
First-ON distributions: baseline 205.461-225.255ms, C1 31.392-37.829ms.
No pseudo-p95 is estimated. Candidate meets the registered <=60ms / >=100ms
strong callback target and <=30ms repeated-ON target, beyond the 50ms MDE.
Foreground B median is 5.126ms higher, below the 38.151ms A/A noise limit;
A median is lower. RSS/private delta increases 75776/18432 bytes are below
their registered A/A bounds. No additional 4K allocation is evident in these
snapshots; zero peak-counter growth does not mean zero allocation. All these
are fixture-specific observations, not physical click-to-screen latency.

Every numerical preview call in the user-path study received actual uint8 and
ran on the GUI thread. Same-key warm re-ON reuses the derived document and
bypasses the getter; a separate post-action getter probe confirms preview HIT.
First ON remains map/metrics HIT + preview MISS. Default hidden Diff, inputs,
source/preview/map/cache identity, generation, selection/order, controls/ROI,
five extra toggle cycles, no stale publish and normal-GC close/drain passed.
Source and driver hashes are frozen; final additions are tests and reporting.

## Exactness, cross-case controls and limitations

The final 45 candidate unit cases cover every actual maximum 0..255 and byte
code, half-step neighboring gains, zero/max maps, Gray/RGB/multichannel,
noncontiguous/negative strides/ROI/read-only views, new independent contiguous
output, uint16/signed/floating fallback, invalid/extreme gains and strict FP
errors, non-image shapes, array gains/subclasses and independent Mask/range/
signed goldens. Every numerical comparison uses byte-exact array_equal.

Production-function microbench repeated all twelve 4K conditions against the
independent pinned-main function: Gray ~59-60ms vs ~2.2-2.4ms, RGB ~179-182ms
vs ~5.6-5.7ms (all normal-GC raw values, maxima 0/127/255, gains 1/1.25,
2 warm-ups +8 observations/function). Pre-product prototype microbench results
are retained separately, not pooled or mistaken for candidate UI speedups.

New Gray/RGB UI cases compare exact source/derived pixels and source-view
center/pixel-scale transitions against the independent baseline renderer,
through first creation, manual view and five OFF/ON cycles at unchanged
1e-8 tolerance. Deliberate pan/zoom negative controls are rejected. An earlier
universal pre/post-scale invariance assumption failed two cases on C1 **and
the same two on unmodified main**. These failed controls remain recorded;
they are not relabeled preservation passes. Fresh reference-vs-candidate
parity passes establish no C1 transition regression, not universal zoom/pan
preservation or resolution of the old #189/#191 oracle issues. An initial
unit/UI basename collision was fixed by a unique UI test filename, not by
suppressing collection or assertions.

Selected existing UI coverage also passes Gray/RGB and RAW/YUV/normalized,
channel/gain/ROI changes, stale worker results, same-path reopen, cache/Keep/
toolbar contracts, normal-GC repeated close and worker-pool ownership. No
historical #191 failed measurement is reclassified, no C2 or async/prewarm
policy is introduced, and no dependency/Qt/queue/lifecycle source is changed.

Exact epoch-bound current-slot/Diff postpaint and scanout stay INCONCLUSIVE.
Observer overhead is uncalibrated. A/B share the same hooks/driver but eight
screening and twenty confirmation samples establish no precise tails. The
synthetic local PNG and warm/uncontrolled OS-cache result is not a performance
claim for SMB, RAW/YUV or all customer formats. Full repository pytest and
peak-private/allocation/reclamation profiling were not run. No merge readiness
or guaranteed customer end-to-end gain follows without independent review.

## Reproduction, evidence and validation

Use CPython 3.10 x64 with repository requirements. Keep separate baseline
checkout at a9ecbf4 and candidate checkout at the measured source above;
the driver verifies the imported package belongs to each requested root.

```powershell
$env:PYTHONPATH = "$PWD/src"
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
python scripts/issue192_benchmark.py --phase AA --baseline ../c1-baseline --candidate . --fixtures temp/c1-fixtures-owner --output temp/c1-AA-owner
# 20/20 pass, including 2 warmups/version
# Publish AA-calibrated MDE/foreground/memory bounds BEFORE starting screening.
python scripts/issue192_benchmark.py --phase screening --baseline ../c1-baseline --candidate . --fixtures temp/c1-fixtures-owner --output temp/c1-screen-owner
# 20/20 pass
# Only after screening gates pass:
python scripts/issue192_benchmark.py --phase confirmation --baseline ../c1-baseline --candidate . --fixtures temp/c1-fixtures-owner --output temp/c1-confirm-owner
# 44/44 pass, 20 observed/version
python -m pytest -q tests/unit/test_issue192_diff_preview.py tests/unit/test_display_gain_core.py tests/unit/test_p3c_display_gain_core.py tests/unit/test_p3b_raw_display.py tests/unit/test_diff_and_statistics.py tests/unit/test_qt_lifecycle_architecture.py
# 103 passed in 1.07s
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest -q -o usefixtures=isolated_qsettings tests/ui/test_issue192_diff_preview_ui.py tests/ui/test_p3a_difference_domains.py tests/ui/test_p3a_difference_main_window.py tests/ui/test_difference_workspace_contracts.py tests/ui/test_difference_cache_panel.py tests/ui/test_difference_cache_toolbar_lifecycle.py tests/ui/test_difference_keep_calculate_lifecycle.py tests/ui/test_multiview_gain_diff_stability.py tests/ui/test_background_work_lifecycle.py tests/ui/test_issue121_qt_gc_lifecycle.py tests/ui/test_wp_c2_yuv_difference.py tests/ui/test_wp_c2_yuv_difference_lifecycle.py tests/ui/test_p3b_raw_display_gain.py tests/ui/test_p3c_display_gain.py tests/ui/test_open_images_registration.py tests/ui/test_large_folder_registration_lifecycle_review.py
# 81 passed in 27.40s
python -m ruff check .
python -m ruff format --check .
# Passed; 351 Python files formatted
python -m mypy src
# Success: no issues in 108 source files
python scripts/check_docs.py
# Documentation contract passed
python -m pip check
# No broken requirements
git diff --check
# Passed
```

Safe JSON: docs/experiments/issue-192-c1-evidence.json (compact generated JSON,
parse rather than diffing as source). Contains all 84 raw scalar records,
prototype/production microbench vectors, frozen calibration, screening and
confirmation gates, paired distributions, source/fixture/raw hashes and
limitations. No logs, settings, local paths, pixel payloads or QObject/array
addresses are published. Local failed-control tests/logs remain ignored.

- Evidence SHA256: `99a8a89d04267576a9a55ce7c06942013c0472143777ab3bb02fad96ee5616b5`.
- Frozen driver SHA256: `ede19f263e326cb12ee1e7e879eddb689eee6d0079159ed305f8404395c7004b`.
- Candidate transform SHA256: `b37c39ddf9e69270ae00e0ffd6ea7f564b9c507b7ef8cb798a2789b225e61fc7`.

Changed: core display_transform.py, independent candidate unit tests, new UI
parity/negative controls, reproducible diagnostic driver, this execution plan
and generated evidence JSON. Implementation is independently revertible and
not stacked on #191. The benchmark is an issue-scoped evidence artifact, not
new production architecture. Qt/System/QA reviews and owner merge decision
remain pending. Connected-owner GitHub activity is ChatGPT-assisted; commits
carry Co-authored-by: ChatGPT <noreply@openai.com>. No human commit rewritten.

Standalone production microbench reproduction (same reference and case order;
no timing assertions, two warm-ups followed by eight observations):

```powershell
@'
import gc, json, runpy, time
from pathlib import Path
import numpy as np
from pixelscope.core.display_transform import render_absolute_difference as candidate
reference = runpy.run_path('tests/unit/test_issue192_diff_preview.py')['reference']
rng = np.random.default_rng(192)
rows = []
for channels in (1, 3):
    for maximum in (0, 127, 255):
        shape = (2160, 3840) if channels == 1 else (2160, 3840, 3)
        source = rng.integers(0, maximum + 1, size=shape, dtype=np.uint8)
        source.flat[-1] = maximum
        for gain in (1.0, 1.25):
            expected = reference(source, gain)
            for repeat in range(10):
                pair = [('baseline', reference), ('candidate', candidate)]
                for version, function in pair if repeat % 2 == 0 else pair[::-1]:
                    assert gc.isenabled()
                    start = time.perf_counter_ns()
                    result = function(source, gain)
                    elapsed = (time.perf_counter_ns() - start) / 1e6
                    assert np.array_equal(result, expected)
                    rows.append(dict(channels=channels, maximum=maximum, gain=gain,
                                     repeat=repeat, warmup=repeat < 2, version=version, ms=elapsed))
Path('temp').mkdir(exist_ok=True)
Path('temp/c1-owner-micro.json').write_text(json.dumps(rows, indent=2))
'@ | python
```
