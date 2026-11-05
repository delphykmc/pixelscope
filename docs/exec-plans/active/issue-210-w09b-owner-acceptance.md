# W09b production integration acceptance

Status: Active; PR #222 remains unmerged.
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
policy is unchanged; no full-suite CI job is added. Full-suite and final static
results will be recorded after the committed source checkpoint.
