# Issue #192: C1 byte-exact Difference preview LUT

Status: Active, owner-authorized candidate; not merged.
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
