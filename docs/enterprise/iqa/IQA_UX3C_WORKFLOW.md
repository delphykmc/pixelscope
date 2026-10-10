# UX-3C — Enterprise-host job workflow and queued publication

## Already implemented and accepted in #156/U6 (#162)

`IqaWindowContribution` owns `IQA > Run IQA` only when PRIVATE SUB
injects an authorized `start_job(source_paths)` callback, a `View > Show
IQA Jobs` checkable dock toggle, an independently visible MAIN status-bar
cue for the most recently updated job, and a **user-selected** action to view
a completed `AnalysisResult` in exactly one separate Analysis Window. It
never starts private workers, auto-opens a result on completion, changes MAIN
image selection or invents an authenticated provider.

UX-3C **does not introduce another dock, registration mechanism or launcher**.
The remaining Handoff-safe integration gap is the path from the PRIVATE SUB
background job callback to Qt GUI widgets without direct cross-thread calls.

## New UX-3C publication surface

`contribution.post_job(IqaJobSnapshot(...))` accepts a validated immutable
snapshot on **any** Python/Qt thread and emits an internal Qt queued signal.
Its target slot executes `publish_job()` on the GUI thread, preserving the
existing U6 status/list/result semantics. The same method can be called by
GUI code but still delivers asynchronously. Pending events are ignored after
`contribution.shutdown()`.

Existing `contribution.publish_job(snapshot)` remains a strict synchronous
**GUI-thread-only** API, retaining the earlier regression that refuses unsafe
worker Qt mutations. Do not call it directly from PRIVATE SUB workers.

Use `IqaJobSnapshot` with `job_id`, nonsecret `label`, `status`, and
optionally `result` **only** for `completed`. Job IDs must identify distinct
requests; the most recently updated status drives the persistent MAIN status
cue. `queued`, `running`, `completed`, `failed` and `cancelled` are
presentation statuses. Whether cancellation, retry, durable readiness, or
client-to-server correlation is actually supported remains a provider
contract obligation in #140 and the PRIVATE SUB adapter. No fake success,
result readiness or cancellation is inferred by this helper.

### Illustrative PRIVATE SUB composition

```python
contribution = IqaWindowContribution(start_job=authorized_start_job)
# Construct/register the contribution with MAIN through U6's documented
# composition root, then publish from PRIVATE SUB's callback:
contribution.post_job(IqaJobSnapshot(job_id, label, "queued"))
contribution.post_job(IqaJobSnapshot(job_id, label, "running"))
# Only when a verified, ready AnalysisResult exists:
contribution.post_job(IqaJobSnapshot(job_id, label, "completed", verified_result))
```

The code above illustrates call boundaries, not a functioning transport.
It does not authorize server reads, nor does it implement a real client.

## Interactive Windows UX-3C preview

The existing `python -m pixelscope_enterprise.iqa.demo --rgb` intentionally
opens **only the standalone Analysis Window**. It has no host/job interface.
`python -m pixelscope_iqa_reference` exercises MAIN's independent Reference
Lite UI, **not** the Enterprise job controller.

To inspect the **actual Enterprise MainWindow contribution**, use the opt-in
source-only synthetic host preview:

```powershell
$env:PYTHONPATH = "src"
& $py -m pixelscope_enterprise.iqa.host_preview --rgb
```

The window title explicitly says SYNTHETIC. It uses the genuine MAIN
`MainWindow`, `IqaWindowContribution` menus/Jobs dock/status button,
real `post_job()` queued Qt delivery from a disposable Python worker and
the real Enterprise Analysis Window. The selected MAIN paths are **ignored**:
nothing is uploaded or analyzed. Optional `--rgb` creates local 4K synthetic
A/B images in a temporary directory for the analysis view.

1. `IQA > Open IQA Analysis` opens the empty independent Analysis Window.
   Close or hide it before continuing.
2. `IQA > Run IQA` creates synthetic job #1, visible via the MAIN status-bar
   IQA Jobs button even while the Jobs dock is hidden. Its list status changes
   `queued → running → completed` without stealing analysis-window focus.
3. Click the status button or `View > Show IQA Jobs`, select job #1, and click
   `View selected result`. The **same** independent Analysis Window opens
   with public-safe synthetic attributes/maps/RGB.
4. Run again to observe #2 `failed`, then #3 `cancelled`: these jobs never
   enable View Result. Runs #4+ repeat completed/failed/cancelled.
5. Hide/reopen Jobs via `View`, continue using MAIN while statuses update,
   then close MAIN to exercise contribution shutdown.

This is a manual **dev preview**, not an authorized enterprise launcher,
actual backend provider, cancel command, production package entry point,
or verified saved Result. MainWindow composition remains a PRIVATE SUB
responsibility; no PUBLIC MAIN or Reference files are modified.

## Acceptance

Run focused Windows Python 3.10 / PySide6 tests in a dedicated process:

```powershell
$env:PYTHONPATH = "src"
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_iqa_ux3c_delivery.py tests/enterprise/iqa/test_iqa_composition.py
& $py -m ruff check .
& $py -m ruff format --check .
& $py -m mypy src
```

Optional real MainWindow U6 smoke, separate process (not routine full suite):

```powershell
$env:PIXELSCOPE_RUN_IQA_REAL_HOST = "1"
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_iqa_composition_main_window.py
Remove-Item Env:PIXELSCOPE_RUN_IQA_REAL_HOST -ErrorAction SilentlyContinue
```

Focused tests simulate queued → running → completed and failed/cancelled
snapshots from a `threading.Thread` with no provider, remote service or
confidential data. They validate visible status while the dock is hidden,
explicit View Result, single Analysis Window, GUI-thread delivery, queued
events discarded on shutdown and safe refusal of subsequent publication.

Production acceptance requires PRIVATE SUB to implement an idempotent request
identifier, verified server result readiness, real auth/transport, capability-
based cancellation (if available), immutable source A/B identity, and
separate release/security approval for any Handoff transfer. **Do not merge
this temporary Handoff branch into PUBLIC MAIN.**
