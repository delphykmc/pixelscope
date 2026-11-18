# RAW dialog GRAY/BAYER layout sizing — PR #245 (2026-11-19)

Status: Draft, awaiting owner Windows retest and final exact-head review.
ChatGPT-assisted. Related issue #236. Based on main merge `431f6d6c` (#244).

## Scope and evidence

The owner reported a Full Suite failure in
`tests/ui/test_p1c_raw_dialog.py::test_raw_dialog_gray_bayer_gray_restores_compact_height`.
The error persisted after the historical #237 screen-bounded native-client
height fix. On the first PR #245 Windows run, **17 passed / 2 failed**:
GRAY 899 px -> BAYER 1011 px -> GRAY 1011 px (expected 899).
The old wait predicate could return with both the dialog height and stale
`sizeHint()` still equal to 1011 px before its deferred refit ran.

After applying the scroll layout correction and requiring the actual measured
GRAY height in the wait predicate, the owner reported **2 passed in 0.97 s**
for the two previously failing geometry tests. The same run printed Windows
`0x8001010D` while in pytest-qt's nested Qt event loop. That COM/RPC symptom
is unresolved and tracked separately by #246, not claimed as a RAW fix.

## Minimal product change

Keep Qt's documented `QLayout.SetMinAndMaxSize` on the `QScrollArea` body
layout, which propagates changing child geometry both when rows expand and when
they shrink. Before computing the automatic dialog size, invalidate the
signal-level group and inner body layout; recompute the size hint bottom-up.
Preserve the existing guard that refuses to override manual dialog resizing.
The action footer remains fixed and the body scrolls on small screens.

An earlier candidate added a `showEvent` zero-delay callback that rebased
`_last_auto_fit_size` to native geometry. Independent review identified a
real P2 race with explicit `dialog.resize()` immediately after `show()`
and a hide-before-callback edge. That candidate is **removed in full**, as
native first-show rebase was not proven necessary for the observed 899/1011 px
case. No new lifecycle callback or state remains.

## Test contracts

- The existing GRAY -> BAYER -> GRAY test keeps its original **1000 ms** budget,
  waits for the **original measured GRAY height** rather than a potentially
  stale `sizeHint` equality, and keeps the black-level content assertion.
- A new regression explicitly resizes immediately after `show()` *before*
  the first queued Qt refit completes, then switches BAYER/GRAY and checks
  manual-size preservation across those event-loop turns.
- Existing 480px small-screen, footer accessibility, scroll area, other RAW
  profile decoding/layout tests remain present; no skips, xfails or extra
  tolerances were introduced.

## Validation gates

Owner Windows: rerun the two selected geometry tests, then all
`tests/ui/test_p1c_raw_dialog.py` and RAW/YUV integration selection.
Review exact revised HEAD, and keep #246 native COM investigations separate.
Do not assert new Full Suite or physical Windows native acceptance without
evidence. Do not merge a Draft PR until the accepted gates are recorded.
