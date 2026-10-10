# Issue #156 H2/U6 — explicit Enterprise IQA composition boundary

Status: PUBLIC-SAFE **handoff implementation proposal**, not PRIVATE SUB
approval, a real model client, or a production installer. PR #161 / U5 owns
the dock lifecycle; this slice owns contribution composition and IQA-specific
settings/job presentation. **PUBLIC MAIN remains unmodified.**

## Ownership decisions

| Layer | Owner | Contract |
| --- | --- | --- |
| Process bootstrap / Base | PUBLIC MAIN | `create_application`, `MainWindow(window_contributions=...)`, `compose_main_window_presentation(..., runtime_contributions=...)` |
| IQA menus / jobs dock / analysis window | Handoff | `IqaWindowContribution` implementing `WindowContribution` and `RuntimeWindowContribution`; one `AnalysisWindowManager` |
| IQA state / window geometry | Handoff with SUB injection | `IqaSettingsFactory`; default remains `QSettings("PixelScope", "EnterpriseIqa")` for legacy continuity |
| Result reader/writer | PRIVATE SUB | Optional injected verified `load`/`save` callbacks; without injection the corresponding file actions remain disabled |
| Job submission / execution / cancellation | PRIVATE SUB | Optional `start_job(source_paths)` callback, not imported into public-safe code |
| Authorization, backend, identity, installer and real launcher | PRIVATE SUB | Never embedded in this handoff, never selected by PUBLIC MAIN |
| Process-wide `QApplication` / AppUserModelID | PUBLIC MAIN default | **No global mutation** or alternate installer identity invented here. Core and Full do not require simultaneous installation |

## Composition sketch (PRIVATE SUB supplies callbacks)

```python
from pixelscope.app.bootstrap import (
    compose_main_window_presentation,
    create_application,
    load_startup_settings,
)
from pixelscope.app.main_window import MainWindow
from pixelscope_enterprise.iqa.composition import IqaWindowContribution

# start_authorized_job, verified_result_loader, verified_result_writer and
# iqa_settings_factory are supplied by the PRIVATE SUB launcher. Not included
# in PUBLIC MAIN/Handoff and deliberately not implemented in this document.
contribution = IqaWindowContribution(
    settings_factory=iqa_settings_factory,
    load=verified_result_loader,
    save=verified_result_writer,
    start_job=start_authorized_job,
)
app = create_application()
repo, application, performance = load_startup_settings()
window = MainWindow(
    application, performance, repo,
    window_contributions=(contribution,),
)
compose_main_window_presentation(
    window, runtime_contributions=(contribution,)
)
window.show()
app.exec()
```

Do not copy this illustrative fragment as an actual launcher until PRIVATE SUB
owns the callbacks, runtime shutdown and installer. `MainWindow.closeEvent`
invokes `contribution.shutdown()` through the existing host lifecycle.

## Job/result state transitions

- `IQA > Run IQA` is installed **only** when an authorized `start_job`
  callback was provided; it receives a tuple of current comparison source
  paths (including `None` placeholders). The contribution does **not**
  validate pair geometry or start workers on its own.
- PRIVATE SUB publishes `IqaJobSnapshot(job_id, label, status, result=None)`
  on the **Qt GUI thread**, with status `queued`, `running`, `completed`,
  `failed` or `cancelled`. Results are accepted only for completed jobs.
  Network/worker threads must marshal updates onto the Qt main thread.
- `View > Show IQA Jobs` opens an extension-owned dock. A completed result
  remains an explicit user choice: select the job, then click **View selected
  result** or double-click. Results never auto-open or steal MAIN focus merely
  because a background job finished.
- `IQA > Open IQA Analysis` opens the independent analysis window even if
  no result has arrived. One manager/window remains authoritative; shutdown
  cancels only UI-local spatial work and **does not cancel SUB jobs**.
- No dedicated settings page or registration slot is added without an actual
  remaining consumer. Existing `SettingsWindowContribution` remains
  available for an optional future PRIVATE SUB settings page.

## Settings and migration boundary

The optional factory must return a fresh `QSettings` handle for an IQA-owned
namespace. It is used for AnalysisWindow geometry and saved dock state and for
initial manager placement. Without injection, the historical explicit
`QSettings("PixelScope", "EnterpriseIqa")` values are preserved so existing
window layouts are not silently reset. The Base/QApplication organization,
name, and preferences remain untouched. The shared PUBLIC
`PlotsDockTitleBar` still uses process-default `QSettings()` for its
own floating geometry key; treat that key as Base-owned UI chrome until a
concrete independent identity requirement justifies a generic injection seam.
Do not access or migrate unrelated MAIN settings through this IQA factory.

## Focused owner acceptance (Windows Python 3.10)

```powershell
$env:PYTHONPATH = "src"
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/iqa/test_iqa_composition.py `
  tests/enterprise/iqa/test_dock_lifecycle.py
& $py -m ruff check .
& $py -m ruff format --check .
& $py -m mypy src
```

Manually confirm: opening IQA with no job, creating queued/running/completed
synthetic statuses, click-to-view result, no auto-open, dock visibility,
separate INI namespace, shutdown and reopen. A PRIVATE SUB integration test
must later cover actual authorized job start/cancellation, settings migration
if one is requested, and production packaging. No live service is part of
routine PUBLIC/Handoff CI.
