# Issue 210: independent review, merge and native failures

Status: Active. Owner: ChatGPT-assisted, 2026-11-12 (Asia/Seoul).

## Authorized sequence

1. Register a safety sleep one hour after work starts, waking six hours later.
2. Independently review PR #227, fix blockers and merge after review acceptance.
3. Leave a durable handoff comment on Issue #210; do **not** close the issue.
4. If review/merge finishes with work capacity remaining, replace the safety timer
   with immediate sleep and wake four hours later, then resume the failure follow-up.
   An OS wake does not itself guarantee this conversation resumes or credits reset.
5. Diagnose and fix the eleven observed Windows full-suite failures, preserving
   native assertions/GC and without broadening CI to full pytest.

## Resume baseline

- Branch: `codex/memo-evidence-cleanup-20261109`, HEAD `930df30b`.
- Tested source: `d7d319cb`; full result 1906 passed, 11 failed, 1 warning (465.00s).
- PR #227 is open/Draft, mergeable as checked on November 12. No merge yet.
- Prior independent agent review failed at the usage limit; it was not acceptance.
- Independent read-only reviewer `/root/independent_memo_review` restarted Nov 12.
- Existing eleven owner untracked documents/diagnostics/fixtures remain untouched.

## Power safety

Registered and checked: **2026-11-12 01:14:38 +09:00 sleep**, **07:14:38 wake**.
Windows tasks `PixelScope-Agent-Sleep-20261112-001438` and
`PixelScope-Agent-Wake-20261112-001438` are Ready. WakeToRun is true for wake;
AC/DC RTC wake timers are enabled. S3 is available. Hardware/power state still
determines actual resume. Runtime script/state are under ignored `temp/agent-power/`.
The previous November 10 wake task produced a wake timestamp; it is not today's timer.

## Failure groups and current evidence

- Nine clipboard failures: Qt OleSetClipboard reports COM OpenClipboard
  `0x800401d0`; reads return empty. Inspect native access/ownership before changing
  production clipboard behavior; do not replace native assertions with a mock pass.
- RAW dialog: GRAY → BAYER → GRAY compact-height test. Inspect actual geometry,
  size hint, screen limits and the `_last_auto_fit_size` predicate.
- Difference RGB geometry: reference/candidate rendering pixel content agrees;
  exact view geometry differs at four of 112 elements. Inspect event/layout settle
  ownership; do not enlarge tolerance or fixed sleep to hide nondeterminism.
- These failure families were reproduced on pristine MAIN `98d2a603` before this
  resume. Reproduce exact current state and separate environment from code defects.

## Validation and handoff

Independent review requested changes for a reproducible destination-revision race:
an external same-document edit between the first digest and archive parsing could
be overwritten. The save now compares the parsed bytes' revision before replace.
The new regression failed before the fix (DID NOT RAISE FileExistsError), then the
archive suite passed **12 tests in 1.32s**; mypy passed **132 source files**.
External bytes and temporary-file/lock cleanup are asserted. Exact-head re-review
is pending; no acceptance or merge is claimed yet.

On November 12, unchanged focused native tests for clipboard, compact RAW dialog,
and Difference preview passed **5 tests in 9.94s**. Current Windows screen is
3440x1392 at DPR 1; native OpenClipboard succeeded (content was not inspected).
This differs from the prior constrained desktop/clipboard-lock environment and
does not establish a code fix for the eleven historical failures. One initial
full run was interrupted to apply the review fix; a new normal-GC full run is
in progress. Record its actual result before any merge decision.

Pending: independent findings, remediation, exact-head acceptance, merge SHA,
Issue #210 comment URL, replacement timer and post-wake work checkpoint. Record
only observed results. All agent commits require the ChatGPT co-author trailer;
GitHub comments/descriptions must say ChatGPT-assisted.
