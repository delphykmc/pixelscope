# RAW dialog native first-show sizing recurrence — 2026-11-19

Status: draft investigation/fix; ChatGPT-assisted. Related issue #236;
historical screen-bounded sizing fix PR #237. Baseline MAIN merge
`431f6d6c184298ad6445525aed37beac6360baad` (PR #244).

## Current evidence and exact failure scope

Owner reports a Windows Full Suite with **one** RAW size/compact-height
failure and all other tests passing; the raw traceback and pass count were not
supplied. An earlier owner report named
`tests/ui/test_p1c_raw_dialog.py::test_raw_dialog_gray_bayer_gray_restores_compact_height`
(the prior message used `test_pc_raw_dialog.py`, an incorrect path).
The failure must not be attributed conclusively to the historical #236
720px/native frame clamp without the current assertion and geometry log.

Existing #237 caps the requested *client* height to the available screen minus
estimated/native chrome, with a scrollable form and fixed footer. The guard
`self.size() == self._last_auto_fit_size` deliberately preserves manual sizes.
However, the remembered auto-fit is initialized **before** the top-level
window is displayed; a native clamp or window-decoration adjustment on first
show can make the actual size differ and later suppress legitimate content-fit
transitions. This is a plausible, testable recurrence mechanism, not yet an
observed reproduction for the owner's current failure.

## Candidate correction

Reconcile the remembered auto-fit authority once after the first
`QDialog.showEvent`, on the next GUI event-loop turn, with actual client
geometry and available-screen size. Leave the existing guard in place for
subsequent user resize. No change to RAW decoding, stride, profile schema,
minimum-height behavior, or file-size validation.

Added a focused Qt test that injects a post-show stale pre-clamp auto-fit
record, checks GRAY→BAYER→GRAY content-height restoration and confirms a
later explicit user resize is not overridden. The original small-screen
footer/scroll and GRAY/BAYER sizing tests remain unchanged and active.
No test skips, tolerance relaxation, or assertion deletion.

## Windows validation gates

1. Run exactly the original failing node with `-vv --tb=long`, preserving
   its initial/final actual height, `sizeHint`, `_last_auto_fit_size`,
   `frameGeometry`, `screen().availableGeometry()`, and Qt platform/DPR
   if any mismatch remains.
2. Run complete `tests/ui/test_p1c_raw_dialog.py`, including the 480px
   small-screen manual-size test and the new native-clamp reconciliation.
3. Run related RAW/YUV/UI tests and then normal-GC Full Suite. Do not call
   the issue fixed from static analysis, a single green rerun, or CI alone.
4. Obtain independent exact-head source review and real Windows native GUI
   acceptance. No manual window-environment test evidence is available from
   this agent runtime.

The previous #244 merge used an owner-accepted exception for the unrelated
one-failure Full Suite. This branch and any Draft PR remain separate.
