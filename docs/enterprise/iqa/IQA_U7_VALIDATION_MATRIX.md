# Issue #156 U7 — IQA Handoff owner/local validation matrix

**Scope:** the temporary PUBLIC-SAFE `handoff/enterprise-iqa-window` branch,
not PUBLIC `main`. This is a validation/CI *ownership* document. It is not
a PRIVATE SUB test execution record, transfer approval, runtime credential,
new GitHub Actions job, or permission to merge Enterprise files into `main`.
Related: #156 U3/U5/U6/U7/U11, #169 UX-3E native acceptance.

## Responsibility and evidence matrix

| Gate | Owner / execution | Contract | Required evidence |
| --- | --- | --- | --- |
| Repo static | Existing MAIN GitHub CI plus developer | Whole-repo Ruff lint/format, strict mypy on `src`, docs/whitespace | Exact SHA + static job conclusions |
| Pure IQA semantics | Developer or authorized Windows owner, **own pytest process** | Numeric model, signed/ROI statistics, ranking, spatial candidates, CSV and handoff manifest | Command, pass/fail/skip counts; no GUI assumptions |
| Native AnalysisWindow UX | **Owner-local Windows Python 3.10/PySide6 6.4.2**, **one pytest process per module** | Real Qt geometry, crop/ROI, chart, export PNG/HTML, dock, event-loop and closing | Module-by-module results, Windows/Python/PySide6, manual UI observations |
| MAIN + Handoff composition | Owner-local Windows, **standalone opt-in real MainWindow process** | IQA menu, status/dock, settings, shutdown, job delivery | Explicit opt-in command, pass/fail, process-exit observation |
| UX-3E E1 native acceptance | Separate PR #169 until merged into the Handoff branch | New lifecycle/visual acceptance additions | Review/merge pin then tests specified by #169, not assumed present here |
| Handoff manifest synthetic | Developer (pure, no Qt) | Hash, ownership, additions/deletions, sibling protection | Synthetic pytest output |
| Handoff real Git protocol | **Opt-in**, separate real Git subprocess test | SHA/tag/blob/import implementation on synthetic repo | Exact Git/Python and passing command |
| PRIVATE SUB deployment | PRIVATE SUB only | Authorized adapter, launcher, dependencies, Inno/portable/native smoke, approved SHA import | PRIVATE SUB release/approval records; **not** inferred from PUBLIC CI |

Do not sum multiple independent Qt subprocess results into a fabricated single
full-suite PASS. Qt native process teardown/GC faults, freezes and pixels that
do not repaint must be recorded as failures or explicit quarantined findings;
a successful Python unit result is not proof of process-exit stability.

## 1. PowerShell preflight

Execute in a clean Handoff worktree, with an installed Python 3.10 environment
containing the pinned project development dependencies and `pytest-qt`.
Use `& $py` in PowerShell (a bare `$py -m ...` is a parser error).
Do **not** run from a PRIVATE SUB checkout to produce public approval logs.

```powershell
git status --short
git rev-parse HEAD
$env:PYTHONPATH = "src"
& $py -c "import sys, PySide6; print(sys.version); print(PySide6.__version__)"
& $py -m pytest --version
```

Capture the exact commit SHA and environment next to each acceptance result.
Run GUI tests with a real Windows Qt platform plugin. If
`QT_QPA_PLATFORM=offscreen` was set for headless work, unset it when making
interactive/real-display assertions:
```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
```

## 2. Fast pure semantics — one pytest process, no native Qt window

```powershell
& $py -m pytest -q --durations=5 `
  tests/enterprise/iqa/test_analysis_model.py `
  tests/enterprise/iqa/test_analysis_insights.py `
  tests/enterprise/iqa/test_spatial_candidates.py `
  tests/enterprise/iqa/test_measurement_export.py `
  tests/enterprise/iqa/test_handoff_manifest.py `
  tests/enterprise/iqa/test_u7_ci_classification.py
if ($LASTEXITCODE -ne 0) { throw "IQA U7 pure-model/contract gate failed" }
```

The fast in-memory handoff manifest tests do **not** replace the real Git
protocol/immutable-tag check. Pure tests must not be mixed into native UI
processes simply to reduce command count.

## 3. Native Qt — one **fresh Python process per test module**

The following modules exist on the U7 baseline and cover currently shipped
Handoff UI behavior. Run each module in its own process to isolate Qt object
lifetimes and native teardown, rather than passing the entire directory to
one pytest interpreter.

```powershell
$nativeModules = @(
  "test_analysis_window.py",
  "test_analysis_roi_chart_scope.py",
  "test_analysis_ux1.py",
  "test_analysis_ux2a.py",
  "test_analysis_ux2c.py",
  "test_analysis_ux3a.py",
  "test_analysis_ux3b.py",
  "test_analysis_ux3b_html.py",
  "test_visual_export.py",
  "test_html_report.py",
  "test_dock_lifecycle.py",
  "test_iqa_composition.py",
  "test_iqa_ux3c_delivery.py"
)
foreach ($module in $nativeModules) {
  Write-Host "IQA native: $module"
  & $py -m pytest -q --durations=5 "tests/enterprise/iqa/$module"
  if ($LASTEXITCODE -ne 0) { throw "IQA native gate failed: $module" }
}
```

Run the optional real-MAIN host separately with the deliberate gate flag;
the module is otherwise **skipped**, not a PASS:

```powershell
$env:PIXELSCOPE_RUN_IQA_REAL_HOST = "1"
try {
  & $py -m pytest -q --durations=5 `
    tests/enterprise/iqa/test_iqa_composition_main_window.py
  if ($LASTEXITCODE -ne 0) { throw "Real MAIN composition failed" }
} finally {
  Remove-Item Env:PIXELSCOPE_RUN_IQA_REAL_HOST -ErrorAction SilentlyContinue
}
```

For UX-3E E1, follow
[`IQA_UX3E_ACCEPTANCE.md`](IQA_UX3E_ACCEPTANCE.md) **only after**
its feature PR is merged and the referenced test module exists at the
exact evaluated Handoff SHA. Never assume a draft PR's test results apply
to another branch's HEAD. Use real screen/4K/high-DPI and repeated
open-close checks as dictated by the current UX acceptance packet.

## 4. Real Git handoff protocol — opt-in separate process

```powershell
$env:PIXELSCOPE_RUN_HANDOFF_GIT_INTEGRATION = "1"
try {
  & $py -m pytest -q --durations=5 `
    tests/enterprise/iqa/test_handoff_manifest_git.py
  if ($LASTEXITCODE -ne 0) { throw "Handoff Git integration failed" }
} finally {
  Remove-Item Env:PIXELSCOPE_RUN_HANDOFF_GIT_INTEGRATION -ErrorAction SilentlyContinue
}
```

Run before security approval/freeze or whenever changing transfer protocol.
This synthetic repository test **does not** grant actual approved-SHA/tag
retention or PRIVATE SUB import authorization. See
[`enterprise/iqa/README.md`](../../../enterprise/iqa/README.md).

## 5. MAIN static CI and change classifier: no hosted Enterprise Qt

Existing `.github/workflows/validation.yml` runs broad, cheap checks
against this PUBLIC-SAFE branch and any target branch as configured:

```powershell
& $py -m ruff check .
& $py -m ruff format --check .
& $py -m mypy src
& $py -m pytest -q tests/unit/test_ci_change_classification.py `
  tests/unit/test_ci_test_groups.py `
  tests/unit/test_ci_workflow_policy.py `
  tests/unit/test_validation_ci_dedupe.py
```

`scripts/classify_ci_changes.py` analyzes path changes only and does not run
tests. In particular:

| Changed path | `classify_paths()` behavior | Operational consequence |
| --- | --- | --- |
| `src/pixelscope_enterprise/iqa/*.py` | `unknown=True`, `local_full_required=True`, `typecheck=True` | Owner/local broad validation and strict mypy; no native Qt pytest scheduled |
| `tests/enterprise/iqa/test_*.py` | `unknown=True`, `local_full_required=True`, but `local_ui_required=False` | **Still a Qt test if importing Qt**; manually run Windows native group; `local_ui_required` does not recognize this Enterprise namespace |
| `docs/enterprise/iqa/*.md` | `docs=True`, no unknown/full requirement for docs-only change | Standard documentation/static validation |
| `enterprise/iqa/handoff_manifest.py` **alone** | Currently outside `VALIDATION_PREFIXES` and workflow path filter | **No automatic GitHub CI trigger is guaranteed**; run targeted security/manifest checks explicitly |
| `scripts/classify_ci_changes.py` or shared `pyproject.toml` | CI-policy/config changes request owner/local broad validation | Do not add arbitrary hosted full pytest as a workaround |

The `unknown` result denotes **owner/local validation required**, not a
failure or a request to dispatch a new GitHub Actions job. `local_full_required`
is advisory evidence for a local merge gate; it does not run an unconstrained
repository-wide pytest on hosted CI. The existing `focused-windows` job
runs only explicit durable `release`, `raw-core`, `yuv-core` test groups
and should **not** be repurposed for IQA Qt tests. CI Static PASS plus skipped
Enterprise tests is **not** a native IQA PASS.

No U7 change to `classify_ci_changes.py`, workflow triggers or MAIN
CI test groups is requested or implemented here. If an Enterprise-specific
hosted native test is eventually desired, it requires a separate issue and
evidence that the runner can reliably handle Qt lifecycle failures.

## 6. Approval evidence / handoff rules

Per-process evidence should retain at least: tested commit SHA, OS and
architecture, Python/PySide6 version (where applicable), command, actual
outcome/pass/fail/skip counts, and human approval reference. The U3/U11
external manifest schema requires `validated_tests` entries; use **actual**
per-process evidence, not inferred or aggregated PASS. Secure approval
requires separate protected immutable Handoff tag/manifest after final
review; branch development merges and PUBLIC MAIN U2/U8 PR merges do not
freeze or approve a Handoff SHA.

PRIVATE SUB must separately exercise real adapter conformance, authorized
Full custom package build/GUI smoke, installer registration/uninstall,
source/result integration and private dependency license policy. Never
put credentials, internal paths, service addresses or backend-specific
details into this PUBLIC-SAFE validation matrix.
