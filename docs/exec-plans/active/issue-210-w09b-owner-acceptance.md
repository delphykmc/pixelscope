# W09b production integration acceptance

Status: Implementation and Windows integration acceptance complete; independent
final-head review remains open. PR #222 remains unmerged.
Date: 2026-11-06. Baseline: `44242e54fdb3b4842d072cae42892498867ad668`.
Main: `98d2a603d879b7989d21207c7615e5b246d10a4b`.

## Scope and observable outcome

Verify the existing production `install_named_review` composition and exact-epoch
load/layout/gain callbacks, close remaining integration defects, and prepare the PR
without merging. A real-byte 3-Finding library must save, reopen in a fresh window
and process, explicitly verify RAW/YUV candidates and selectively restore 2/4/6
sources with ROI/Line/pair/recipe/physical views. No implicit Difference Calculate
or historical-to-live metric republication may occur during restore.

The owner reports an earlier full-suite PASS; retain that as owner-reported
baseline evidence, not a count/SHA we executed. Any code changes require new focused
and applicable full native Windows evidence under normal GC.

## Work slices

1. Inspect production entrypoint, source verification/consent, capture fence,
   controller epochs, canonical authority, W04/W05 view staging and Difference.
2. Add native integration tests using disk RAW/YUV bytes, the installed coordinator,
   genuine workers, explicit candidate/profile consent and real save/reopen.
3. Fix evidenced integration defects with owner-scoped hooks, deterministic
   teardown and regression tests; preserve Session/Selected/Page/residency authority.
4. Actual Windows 3-Finding save/process restart/selective restore; disclose any
   hardware/SMB/locked-file cases not run. Focused/full tests, static/docs/pip checks.
5. Remove temporary PR-only native workflow after its evidence is recorded, update
   cumulative docs and handoff, publish exact-head evidence and ready the PR.

No packaging, source-file mutation, automatic relink, W10 reports, merge or sleep.
Keep diagnostic harness/logs in ignored `temp/w09b-integration-20261106/`.

## Observed implementation and focused evidence

The baseline already installs the coordinator after W05/W06, forwards foreground
success/error plus geometry/first-frame/display-preview terminal signals, filters
the current pending epoch, cancels on user navigation, and shuts down before viewers.
The remaining work therefore verifies these seams rather than duplicating them.

Two production defects were reproduced and fixed:

- The strict W04 value object omitted the actual two-image `Side by Side` layout,
  causing Add Finding to fail before capture. Accept that existing canonical layout.
- W04 restored Sync Off in the view but left the MainWindow Sync QAction checked.
  Mirror the applied state with signals blocked, then refresh action descriptions;
  do not emit a second geometry mutation.

The new Windows Qt regression starts independent save and restore interpreters,
using six real synthetic disk files (RAW12 uint16 LE and YUV420). Three Findings
cover 2/4/6 sources, ROI/Line, display gain, physical zoom, Sync On/Off and the
Difference pair/recipe. It rejects a declined relocation, approves each profile and
candidate, hashes/decodes on real workers, saves via CAS, opens without workspace
mutation, and activates each verified Finding. A Python code-object call observer
proves zero Difference Calculate calls, including the W05 owned callback route;
no live result/token/worker is published. File/profile/confirmation dialogs are
automated at the dialog boundary; this is actual Windows native Qt automation,
not an unassisted human clicking session. Rendered 2/4/6 views are retained as PNGs.

Focused command (CPython 3.10.11 / PySide6 6.4.2, normal GC):

```powershell
python -m pytest tests/ui/test_w09b_named_findings_roundtrip.py tests/ui/test_w09b_production_wiring.py tests/ui/test_w04_review_view_state.py tests/unit/test_review_view_state.py tests/unit/test_w09b_review_guards.py tests/unit/test_w09b_native_decoder.py tests/unit/test_w09b_review_workflow.py -q --basetemp=C:/Users/Public/Documents/ESTsoft/CreatorTemp/pixelscope-w09b-focused6-20261106
```

Observed: **80 passed in 16.94s**, exit 0. The rendered four-source Review view was
visually inspected: selected Finding, per-source verified labels, applied status,
ROI/Line overlays and distinct physical zooms are present. A draft test that
replaced a QObject class method caused a PySide signal-connection access violation;
that test instrumentation was removed, not suppressed by disabling GC or tests.

The temporary PR-only native workflow is removed after the recorded baseline run
42057223477 (Ubuntu 53 passed, Windows 53 passed). The permanent change-scoped CI
policy is unchanged; no full-suite CI job is added.

## Final validation checkpoint

Source/test commit: `1536689f839765dd135b20a8024e694524d26d33`. Later acceptance
documentation changes do not change `src/`, `tests/` or runtime configuration.
Commands below used the repository's existing `.venv/Scripts/python.exe` from
the isolated PR checkout, with its `src` on `PYTHONPATH` for application launch.

| Command | Observed result |
| --- | --- |
| `python -m pytest -q --basetemp=C:/Users/Public/Documents/ESTsoft/CreatorTemp/pixelscope-w09b-full-20261106` | **1,951 passed, 1 warning in 479.22s**, exit 0; normal automatic GC, actual Windows |
| Focused command above | **80 passed in 16.94s**, exit 0 |
| `python scripts/check_docs.py` | Documentation contract passed, exit 0 |
| `python -m ruff check .` | No diagnostics, exit 0 |
| `python -m ruff format --check .` | 400 files already formatted, exit 0 |
| `python -m mypy src` | Success: no issues found in 133 source files, exit 0 |
| `python -m pip check` | No broken requirements found, exit 0 |
| `git diff --check` | No whitespace errors, exit 0 |

The one full-suite warning is the expected duplicate `data/measurements.csv` ZIP
entry created by `test_reject_manifest_tamper`. No test was skipped or disabled to
obtain this result. Logs: ignored `full-1536689f.log` and `focused6.log` under the
evidence directory. The owner-reported earlier full PASS remains separate.

An additional ignored cache diagnostic (`python -m pytest
temp/cache-probe/test_cached.py -q`, outside-Git basetemp ending
`pixelscope-w09b-cache-probe3-20261106`) passed **1 test in 11.88s**, exit 0.
It explicitly computes a Difference map after the first activation, confirms its
cache, resets the call observer, then restores later Findings: still no implicit
Calculate or live historical result republication. This diagnostic is supplemental
to, not part of, the committed full-suite count.

Exact-source CI is successful: change-scoped validation run **42061286090**,
User Guide **42061286187**, pinned Windows screenshot comparison **42061286141**.
Hosted Focused Windows pytest was intentionally skipped by the permanent selector;
the local native Windows tests above provide the applicable GUI/full evidence.
Rendered two/four/six-source restored views were inspected for the Finding list,
source verification, applied status, physical zoom and ROI/Line overlays.

## Readiness, constraints and attribution

The four requested integration gates are implemented and tested. Review preparation
does not supply an independent final-head code approval: the earlier independent
review only covered `4750f8b...`; the integrated production callbacks and these fixes
still require final independent review before merge. No merge is performed.
SMB/Windows locked-file behavior, multiple physical monitors/DPI transitions and
large multi-4K memory/latency remain unmeasured environment cases, not inferred
from these synthetic 64x48 native tests. PNG/JPEG Findings and W10 reporting remain
outside W09b. Existing Session v1, numerical algorithms and packaging are unchanged.

Changed implementation files: `core/review_view_state.py` and
`ui/review_main_window_adapter.py`; regressions: the W04 value-object unit test,
W09b authority guards and new `tests/ui/test_w09b_named_findings_roundtrip.py`.
Guide/handoff/current-state/spec/architecture and this plan carry the acceptance
record; the temporary native workflow is removed. Base-to-head durable-document
statistics were inspected for unexpected contractions; existing cumulative content
is retained. Commits use owner-authenticated Git with
`Co-authored-by: ChatGPT <noreply@openai.com>`; PR activity is labelled
**ChatGPT-assisted**. Existing human commits are not rewritten.
