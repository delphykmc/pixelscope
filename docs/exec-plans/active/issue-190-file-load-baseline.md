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
