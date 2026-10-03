# Test execution lanes

PixelScope separates deterministic functional coverage from the long-lived native Qt
lifecycle canary tracked by Issue #81. The split exists because one monolithic pytest
process repeatedly creates and destroys large PySide6/pyqtgraph object graphs in a
workload that has shown stochastic Windows native failures even when the exact same
source tree later completes successfully.

This document defines execution policy only. It does **not** classify the Issue #81
native defect as fixed or harmless.

## Fresh-process grouped functional lane

Use the repository runner for full functional validation:

```powershell
.\.venv\Scripts\python.exe scripts\run_test_batches.py
```

The runner deliberately starts a new Python process for each batch:

1. `tests/unit`, `tests/integration`, and `tests/performance` run together as the
   `non-ui` batch.
2. `tests/ui/test_*.py` files are discovered recursively, sorted by repository path,
   and divided into deterministic groups of eight files by default.
3. Every UI group runs in a fresh `python -m pytest` child process.
4. Each child process writes a log and JUnit XML file below
   `.test-results/batched/`.
5. A subprocess-level timeout bounds a native hang. The default is 600 seconds per
   batch and can be overridden explicitly.
6. The runner continues with later batches after an assertion failure, process crash,
   or timeout so the owner can collect as much functional feedback as possible.
7. The overall runner exits nonzero if **any** batch did not pass.

A later successful batch or separate rerun never converts an earlier native crash or
timeout in the same validation run into PASS. Crashes remain failed/incomplete
coverage evidence.

Useful commands:

```powershell
# Inspect the exact deterministic plan without running tests.
.\.venv\Scripts\python.exe scripts\run_test_batches.py --list

# UI lane only.
.\.venv\Scripts\python.exe scripts\run_test_batches.py --scope ui

# Non-UI lane only.
.\.venv\Scripts\python.exe scripts\run_test_batches.py --scope non-ui

# Temporarily tune process lifetime while investigating Issue #81.
.\.venv\Scripts\python.exe scripts\run_test_batches.py --ui-batch-size 4

# Override the per-batch subprocess hang bound when a known slow environment needs it.
.\.venv\Scripts\python.exe scripts\run_test_batches.py --timeout-seconds 900
```

The batch size is a process-lifetime bound, not a test-selection policy. New UI test
files are included automatically and must not require marker maintenance merely to
enter functional coverage.

## Native lifecycle canary

Keep the original single-process suite available separately:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

This monolithic command is the Issue #81 canary. It intentionally preserves normal
automatic Python GC and accumulated Qt/PySide6/pyqtgraph lifetime pressure across the
entire suite. It is useful when changing QObject ownership, worker teardown,
pyqtgraph disposal, GC-sensitive code, Qt dependencies, or Issue #81 itself.

A stochastic native failure from this canary must be reported with the exact source
SHA, dependency versions, process exit/dump evidence when available, and detection
stack. The victim test or detection stack must not be treated as the first corruptor
without independent evidence.

## What this policy does not allow

Do not make the functional lane appear green by:

- disabling automatic cyclic GC;
- inserting blanket `gc.collect()` calls;
- adding arbitrary sleeps or inflated pytest waits;
- suppressing fatal process exits;
- automatically retrying a crashed batch and erasing the first failure;
- globally waiting/cancelling unrelated application pools at every test boundary; or
- classifying a native crash or timeout as SKIP/XFAIL/PASS.

The grouped lane reduces accumulated process lifetime so ordinary feature validation
can complete deterministically. The monolithic canary remains the place to observe
whether Issue #81 still reproduces under maximum lifecycle accumulation.

## Artifacts and exit classification

`run_test_batches.py` records one `.log` and one JUnit `.xml` per batch plus
`summary.txt` under `.test-results/batched/` by default. Generated results are not
repository source and are ignored by Git.

Standard pytest exit codes retain their pytest meaning. On Windows, structured
exception process exits such as `0xC0000005` are reported as `native-crash`. POSIX
signal termination is reported separately. Unknown non-pytest nonzero exits remain
`process-error`. A subprocess timeout is reported as `timeout`.

All of these statuses except `passed` make the overall command fail.

## Relationship to Issue #81

The grouped lane is validation architecture, not a root-cause patch. Issue #81 remains
open until the native first-corruptor is understood or the lifecycle defect is
otherwise demonstrated resolved. If real interactive PixelScope usage begins to show
the same native failure, production lifecycle investigation takes priority over test
process isolation.
