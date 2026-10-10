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
