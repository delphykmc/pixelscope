# RAW dialog GRAY/BAYER layout sizing — PR #245 (2026-11-19)

Status: **MERGED** — PR #245 integrated into `main` as
`0097a0c3d08fa16855f98669517321f1ff0030eb` (final PR head
`d7634172fdd97c060abaab2049ddfcec4c714504`). Owner-directed acceptance
after focused Windows PASS and GitHub CI 3/3 success; no final-head Full Suite
or native-COM-clean claim. ChatGPT-assisted. Related issues #236 and #246.
Original implementation base: `431f6d6c` (#244).

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

## Final disposition and remaining evidence boundaries

- First Windows selection at earlier PR head: **17 PASS / 2 FAIL**; both
  failing GRAY/BAYER compact-height tests demonstrated the stale-size condition.
- Intermediate PR head `59782363`: owner reported the two originally failing
  geometry tests **2 passed in 0.97s**; the same run also printed Windows
  `0x8001010D`, even though pytest continued. This remains historical evidence.
- Final head `d7634172`: owner explicitly reported the two requested focused
  tests **PASS**, including immediate manual-resize preservation. No exact
  console summary from that final run was retained in this execution record.
- GitHub actions at final head: change-scoped, User Guide and pinned Windows
  screenshot comparison all **SUCCESS (3/3)**. These do not substitute for a
  Windows Full Suite.
- Independent source review at earlier head `59782363` identified the
  queued first-show rebase and 1000→3000 ms regression timeout as P2 issues.
  Both changes were corrected at final head and independently inspected during
  merge; **no separate final-head reviewer approval was recorded**.
- Owner explicitly instructed PR #245 merge with the remaining native
  diagnostic independent; merge commit `0097a0c3`. No Full Suite PASS, no
  final native-clean claim, no COM suppression or test skipping.

## Separate native diagnostic (#246)

[Issue #246](https://github.com/delphykmc/pixelscope/issues/246)
records historical Windows `0x8001010D` reports. The subsequent
[independent review](https://github.com/delphykmc/pixelscope/issues/246#issuecomment-6991365696)
recommends proportional monitoring: **no reported native recurrence on the
final #245 commit, but no verified comprehensive native-clean log either**.
The native COM caller is unknown. The event is not proven a product crash and
does not retroactively invalidate the confirmed RAW compact-height fix.
Preserve SHA/command/pytest result/process exit code on a new occurrence;
escalate native diagnosis if an event recurs on current code or is associated
with an abnormal exit, user-visible malfunction, hang or relevant failing test.
No blind re-runs or compulsory debugger capture for unrelated merges.
