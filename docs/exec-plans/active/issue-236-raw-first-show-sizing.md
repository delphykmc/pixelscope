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

## Windows owner run: observed failure and correction

Owner ran the Draft PR #245 focused selection (3 modules). Result:
**17 passed, 2 failed, 8.22 seconds**, plus a logged Windows native exception
`0x8001010D` during the simulated small-screen Qt wait loop. The exception
message appeared while pytest continued to the normal assertion summary;
it does not by itself establish the cause of the two assertions.

Both failed nodes were the newly added native-fit regression and the unchanged
`test_raw_dialog_gray_bayer_gray_restores_compact_height`. The dialog grew from
899 px (GRAY) to 1011 px (BAYER); after returning to GRAY it reported 1011 px.
The test's `waitUntil` accepted an **old 1011 px sizeHint** while the deferred
`QTimer.singleShot(0, _resize_dialog_to_content)` callback could still be
pending. Therefore the earlier wait condition was not a reliable proof that
the compacting layout transition had finished.

Qt documents that a resizable `QScrollArea` containing a widget with a dynamic
layout may need `QLayout::SetMinAndMaxSize` to propagate content changes.
The follow-up uses that documented constraint on the body layout and explicitly
invalidates the signal-level/inner layout before computing an updated height.
Both GRAY-return tests now wait for the **original measured GRAY height**, rather
than merely comparing current height against a potentially stale sizeHint. The
test and source changes are separate hypotheses: if the test still fails on
Windows after this change, collect inner body/layout/stack hints and geometry
before revising further. No arbitrary GUI delay or tolerance relaxation added.

Microsoft's name for HRESULT `0x8001010D` is
`RPC_E_CANTCALLOUT_ININPUTSYNCCALL` (an outgoing COM call attempted while
dispatching an input-synchronous call). The shown Python stack is a pytest-qt
nested event loop, **not an identification of the offending COM caller**.
Investigate independently using an isolated Windows control, session lock state,
and native exception diagnostics. Do not suppress the exception or classify it
as harmless based solely on a continued pytest run.

Sources:
- https://doc.qt.io/qt-6/qscrollarea.html
- https://learn.microsoft.com/en-us/windows/win32/com/com-error-codes-3
