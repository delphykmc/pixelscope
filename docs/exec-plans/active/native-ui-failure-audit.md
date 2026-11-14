# Recurring native UI failures — 2026-11-14

Status: active; merge hold. ChatGPT-assisted. Parent #230.

## Scope and owner decision

Owner approved UI-01/UI-02 necessity/screenshots but requested that recurring
eleven failures not be dismissed because unchanged MAIN also fails. Preserve
historical bounded completion records; they prove their dated runs, not a cause
or permanent resolution. No merge until remaining risks are explicitly resolved.
Investigate clipboard access, RAW sizing and Difference geometry separately.
No timeout/tolerance inflation, GC suppression, clipboard mocks replacing native
acceptance, dependencies, packaging or unrelated Memo changes.

## Current evidence

Candidate 03f798df: normal-GC full pytest 1961 passed, 11 failed, one intentional
ZIP warning, 513.73s. Seven-module native retry:20 passed/10 failed18.24s.
Unchanged MAIN603626d1 separate checkout, same modules:19 passed/11 failed20.00s.
Failure node sets of candidate full and baseline match exactly; this does not
establish that the failures are harmless or the full gate passed.

Nine failures contain OleSetClipboard E_ACCESSDENIED. A fresh Python process
before importing Qt or PixelScope calls only Win32 OpenClipboard(NULL), fails
with error5, and finds a visible window station. Both ordinary and elevated
execution reproduce this. No clipboard contents are read or logged. This
separates current native access denial from application QWidget teardown;
underlying host access policy is not yet identified and copy acceptance is blocked.

RAW standalone probe on1024x720/DPR1: before show280x927/last-auto280x927;
after show280x749/hint262x899. BAYER hint1011 while size remains749, return to
GRAY hint899/size749. OS sizing causes size != last-auto, so the content-fit
guard misclassifies it as a user resize. This is an actionable small-screen UI
defect, independent of MainWindow/Viewer creation. Bound auto sizing to available
screen client height, retain scrollable body/fixed footer and respect manual resize.

Difference RGB parity compares two MainWindow renderer runs, differing at4/112
geometry values while pixel assertions pass. Snapshot waits only layout-refit
then10ms; inspect actual viewer geometry/request fences before any change.
Fresh retry pass does not establish a cause. Independent read-only review active.

## Confirmed fixes and focused evidence

RAW regression on simulated480px available height failed before the fix
(1 failed6.02s). Screen-bounded sizeHint and auto-fit now preserve the footer,
scrollable content and manual sizing. Original content round-trip still requires
stack expansion/return; only the outer-height growth is conditional on screen
capacity. RAW10 tests passed0.89s; direct720px probe now fits689px and last-auto
matches the actual size throughout GRAY/BAYER/GRAY.

Difference tracing reproduced4/112 geometry mismatch with valid physical
measurements and idle geometry timers. At first Diff-off, physical target changed
297.47596% to240.73668% in one run. set_documents saved the old range then
_apply_range remeasured it after viewport relayout, conflating range and physical
scale. Preserve-view now snapshots physical percent and reference center before
layout, applies through canonical zoom with range-sync guarded, and checks target
document ID/generation/source versions. Saved-range restoration and SyncOff paths
remain unchanged. No new QObject graph or numerical/source change.

Focused command:
`.venv/Scripts/python -m pytest -q --tb=short tests/ui/test_p1c_raw_dialog.py
tests/ui/test_issue192_diff_preview_ui.py tests/ui/test_w01_physical_zoom.py
tests/ui/test_issue75_difference_geometry.py tests/ui/test_memo_roi_workflow.py
tests/ui/test_w04_review_view_state.py
--junitxml=temp/native-ui-fix-focused-20261114.xml`:
**73 passed in19.68s**. Independent working-diff review found no actionable source
issue. New two/three/two tile regression checks physical percent, reference center
and an independent Qt coordinate oracle. Broader final validation follows.

## Work and validation

1. Add regression for screen-bounded RAW sizing and manual-resize preservation;
   preserve actual content expansion/return through scrollable body.
2. Trace Difference geometry per transition with timers/result authority and
   correct an evidenced production or test readiness defect only.
3. Run applicable native/UI/lifecycle checks and broad tracked static/docs gates.
   Record blocked native clipboard acceptance honestly; do not rerun complete
   pytest merely to obtain an intermittent pass.
4. Obtain exact-source independent review; preserve owner UI approval separately
   from technical merge readiness. GitHub updates marked ChatGPT-assisted and
   agent commits carry ChatGPT coauthor. Existing owner untracked files untouched.

Temporary raw/native probe: temp/native_ui_failure_probe.py. Full/retry/baseline
XML/logs: temp/ui01-ui02-merge-20261114.*, temp/ui-merge-native-focused-20261114.*,
temp/ui-merge-baseline-focused-20261114.*. No product clipboard content captured.

## Exact-source broader run and final contract checks

Source ffa2aad03608e7625e322825dffdc9ab1eae2cc8 normal-GC Windows:
`.venv/Scripts/python -m pytest -q --tb=short
--junitxml=temp/native-ui-fix-full-20261114.xml`:
**1964 passed,10 failed,1 intentional ZIP warning in463.84s**, exit1.
RAW and Difference parity now pass. Nine clipboard failures remain; the tenth
is test_source_primary_cycle's three-source raw-range endpoint comparison.
Do not call this full validation successful.

Primary trace verifies physical percent57.391826923076 and reference center160,120
unchanged while integer ViewBox widths redistribute191px to192/189/192px.
Different viewport widths imply different range endpoints at the same scale.
The test now checks every retained document's measured scale/center after layout
and geometry timers settle, retaining upload0/source-order/selection checks.
It uses0.5% physical-scale accuracy and center absolute1e-8 with rel0; no timeout
or old tolerance was inflated. Independent review confirms this contract change.

Seven-module focused command above plus tests/ui/test_source_primary_cycle.py:
**85 passed27.08s** (temp/native-ui-fix-final-focused-20261114.xml). Final stricter
center assertion: `.venv/Scripts/python -m pytest -q --tb=short
tests/ui/test_source_primary_cycle.py
--junitxml=temp/native-ui-primary-final-20261114.xml`: **12 passed9.90s**.
Product source is unchanged since the full run; later changes are test/docs only.
No post-test-change full-suite result is claimed.

Tracked409 Ruff/format and mypy134 passed; source/tests Ruff/format355 and mypy134
also passed after final test edit. Docs contract and strict MkDocs passed before
the final evidence-only closeout. Broad dot-Ruff still includes preserved owner
untracked diagnostics; it is not a tracked-code PASS.

Production bootstrap/isolated settings QWidget.grab captures under
temp/raw-screen-fit/{before,after}.png with JSON source/hash/geometry metadata:
MAIN frame280x780 exceeds available1024x720; fixed frame280x720 fits, scrollable
body retained. These are widget renders, not physical OS-screen acceptance.
Plain native probe additionally reports no open clipboard window and current-job
UI restrictions0; this does not identify the host's exact access restriction.

Draft fix PR #237 on #234; investigation #236. UI approvals for #232/#234 remain
valid, technical merge is held for unresolved native clipboard acceptance.
Exact source independent review accepts both corrections; no lifecycle safety or
full-PASS claim is inferred. Historical #210 remains closed and preserved.
