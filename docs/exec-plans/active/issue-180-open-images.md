# Issue #180: Open Images and Recent registration follow-up

Status: Active

Owner: ChatGPT, under owner authorization

Branch: `codex/issue-180-open-images`

Last updated: 2026-10-16

## Goal and scope

Finish the remaining production Open Images/Recent Images registration path from
Issue #180. Return control to Qt while filesystem discovery runs in the existing
RegistrationController pool, then register in bounded GUI slices, replace Selected
in existing natural filename order, and defer Recent persistence until a source
frame has painted.
Preserve folder/drop additive behavior, RAW/YUV profile dialogs, explicit same-path
reload/generation, cancellation, serialized requests and shutdown ownership.

No new worker pool, numerical algorithm, integer pipeline, packaging change or
Enterprise IQA dependency. Standalone MainWindow composition retains its existing
synchronous registration API; production command routing uses the owned controller.

## Audit

At `main@f549c24342ce05ed96f7fa9ae3e0597e90324f1a`, #180 is the remaining open
Base optimization issue. Test-runtime #100/#113 are already closed completed.
Issue #81 is a separate unresolved native-lifecycle investigation; passing recent
tests alone does not establish its incident root cause or justify closing it.

PRs #181 through #186 delivered initial load/preview, passive Difference, Files drag
coalescing, exact uint8 Histogram, Primary styling and stable Histogram/Analysis
presentation. Issue #180 still lacks its full human cold/warm/file-surface matrix
and its Open Images/Recent command unification; do not mark those as complete.

## Baseline measurements

Pinned Windows CPython 3.10.11, NumPy 1.24.4, OpenCV 4.8.1, PySide6 6.4.2,
offscreen Qt. Synthetic RGB8 3840 x 2160 PNGs, empty catalog, one warm-up then ten
fresh-window repetitions for each batch size. File dialog is stubbed; first paint
is the existing viewer `first_frame_painted` signal, not worker completion or
monitor scanout. cProfile covers one command dispatch in each batch.

| Input | command dispatch p50 / p95 ms | first Qt viewport paint p50 / p95 ms |
|---|---:|---:|
| 1 file | 34.91 / 38.79 | 186.13 / 209.06 |
| 32 files | 247.05 / 273.78 | 878.15 / 919.28 |

Single-file profile: Recent QSettings sync used 18 ms of a 41 ms command.
32-file profile: 314 GUI `Path.resolve` calls consumed 192 ms of a 269 ms command.
These identify avoidable GUI work, not a claim about physical disk cold-cache
latency or human perceived speed. Probe remains ignored under `temp/`.

## Implementation

1. Add an explicit replacement-selection intent to the existing serialized
   registration request; keep the current default additive drop intent.
2. Route production Open Images and Recent Images through a shared MainWindow
   command and that request intent. Keep UI profile confirmation on the GUI thread.
3. Use existing per-record registration, reload semantics, deferred history,
   cancellation/generation and close handling; do not auto-schedule Drop Difference
   for these explicit Open commands.
4. Add production-composed worker-barrier, replacement/order/reopen, empty/cancel,
   queued request, first-paint history and shutdown coverage. Reconcile only tests
   that currently rely on the old synchronous command completion.
5. Remeasure the same probe, run applicable/static/docs checks and create a separate
   reviewable PR. Keep #180 open while required code/evidence is still pending.

## Validation

Test Windows production composition plus existing registration, Recent, RAW/YUV,
input, Quick Compare, source residency and native-lifecycle regressions. Use normal
automatic GC, no timing threshold, no timeout inflation or fixture masking.
Run Ruff/mypy/pip/diff checks, docs contract and strict User Guide build. Full pytest
is owner/local only and required at the integration checkpoint, not added to CI.

## Progress

- 2026-10-16: Audited open issues and merged PRs, inspected source/call sites/tests,
  and measured the synchronous command path before implementation. Existing owner
  installer/GC files remain untouched.
- 2026-10-16: Added replacement-selection intent to the existing registration
  request, shared MainWindow command routing and Recent delegation. Preserved
  natural order, reload generation and additive Drop intent. The new tests cover
  GUI event progress during blocked discovery, staged MRU before paint, ordered
  replacement, deduplication, real same-path content reload, queued Open/Drop,
  page-bounded loading, cancel and skipped RAW profile.
- Existing production Recent tests now use actual decodable files and wait for
  registration completion; fault injection targets staged persistence. The folder
  observer test prohibits directory enumeration instead of patching a removed,
  unused import. No timing tolerance or timeout was increased.
- Applicable input/registration/Recent/YUV selection: **82 passed in 35.09s**.
  RAW/Quick Compare/native-lifecycle selection: **40 passed in 25.03s**. Initial
  new-test assumptions about supplied order and object identity on reload were
  corrected to the existing natural-order/catalog-ID/generation contracts. A Qt
  callback error after that failed test did not reproduce in the isolated queued
  test or the corrected passing selections; no lifecycle suppression was added.
- Initial full run was stopped after installer harness failures because
  `sandbox-runner.ps1` correctly refuses uncommitted production inputs. Commit the
  tested implementation before rerunning that required integrity check; do not
  weaken its HEAD check or change installer behavior.

## After-change measurements

Same synthetic Windows/offscreen probe and repetitions as above:

| Input | command dispatch p50 / p95 ms | first Qt viewport paint p50 / p95 ms |
|---|---:|---:|
| 1 file | 0.66 / 0.80 | 182.71 / 203.70 |
| 32 files | 1.41 / 2.88 | 696.76 / 759.43 |

The command now dispatches existing registration workers instead of synchronously
performing discovery/Recent sync. The single-file first-paint difference is small
and is not claimed as a meaningful improvement. The 32-file observation improves
first Qt paint while retaining the same bounded first-page load. No cold-cache,
monitor scanout, human matrix or universal speedup claim is made.
