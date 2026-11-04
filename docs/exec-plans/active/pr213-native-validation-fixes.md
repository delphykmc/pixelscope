# PR #213 native validation follow-up

Status: Complete (implementation and automated validation; no merge)
Owner: ChatGPT-assisted implementation
Branch/PR: https://github.com/delphykmc/pixelscope/pull/213
Last updated: 2026-11-04

## Goal and scope

Resolve the two reproducible Difference UI failures found by the owner-requested
Windows full-suite check at `e5b7af1f065ce84cb1dfb7e34a7d8d092309be2e`.
Preserve native numerics, explicit Calculate export authority, cancellation and
stale-result rejection. No merge, packaging or unrelated UI changes.

## Findings and changes

- `DifferencePanel._request_preview_render` reads the metric request ID even when
  a cached-map display precedes metrics. Initialize empty request provenance in
  the constructor and explicitly reject it for frozen capture. Existing threaded
  display regression also asserts no metric/export permission is manufactured.
- The old YUV test injected an anonymous result after channel cancellation and
  expected a cache write. This conflicts with the current worker-identity guard
  and the architecture's cancellation authority boundary. Exercise a real held
  request, cancel it through the channel control, then deliver a queued success.
  Assert no map/metric cache write, publication or export permission. Keep the
  production worker guard intact; valid channel-map reuse remains separately tested.
- The full run's Git-guard failure came from placing `--basetemp` inside a Git
  repository. Use a unique temp directory outside Git for subsequent validation;
  do not alter production or Git-guard assertions for this environment issue.

## Validation and completion gates

Run Difference/YUV/export/lifecycle focused tests, all QUALITY static gates, and
the complete Windows pytest suite with normal GC. Record the native COM diagnostic
if it recurs; no suppression or timeout changes. Keep full logs/JUnit outside
tracked source. Update this record with observed results before the attributed
commit and PR comment. Independent review and merge remain owner decisions.

## Progress

- Focused Difference/YUV/export/lifecycle checks: 101 passed, 1 intentional ZIP
  tampering warning in 9.02s. Ruff lint/format, docs, mypy (112 source files),
  dependency and diff checks pass.
- An initial post-edit full run was stopped after discovering that sandbox-runner
  integration tests deliberately reject uncommitted production edits. Commit the
  tested fix first and rerun all tests on a clean HEAD; do not weaken that guard.
- Windows COM diagnostic `0x8001010d` recurred during early event processing in
  that interrupted run. No source cause has been established; retain the evidence
  and report it separately from deterministic test failures.

## Completion evidence

Full clean-HEAD Windows run at
`c301c0c00b1a8aabdbcae6d4cf07f11173f78506`, Python 3.10.11 / PySide6 6.4.2,
normal GC, no test exclusions or timeout changes:

```powershell
python -u -m pytest -q --basetemp=C:/Users/Public/Documents/ESTsoft/CreatorTemp/pixelscope-pr213-clean-full-20261104 --junitxml=../pr213-clean-full.xml
```

Observed: **1645 passed, 1 warning in 529.38s**, exit 0. The warning is the existing
intentional duplicate ZIP member in the tampering test. Both reported UI failures
and the Git-root test pass. The COM `0x8001010d` diagnostic recurred during Qt event
processing; the process continued to completion. Its cause remains unverified and
is not claimed fixed. No manual GUI rerun, packaging or multi-DPI check was added.

Local evidence is in ignored `temp/native-acceptance-20261104/`, including
`pr213-clean-full.log`, `pr213-clean-full.xml`, exit status and focused test logs.
The completion-record commit changes only this Markdown file after the tested
source commit. PR attribution uses the configured owner identity plus
`Co-authored-by: ChatGPT <noreply@openai.com>`; the PR comment is ChatGPT-assisted.
Independent review of the follow-up diff and any merge remain owner decisions.
