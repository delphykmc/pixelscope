# Issue 210: independent review, merge and native failures

Status: Complete for review, merge and bounded eleven-failure verification.
Owner: ChatGPT-assisted, 2026-11-12 (Asia/Seoul). The final completion record below
supersedes earlier pending/review/automatic-continuation statements. Issue #210
remains open for its broader scope.

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

### Fixed-head completion, November 12

Source/test SHA: `5cc638357053418574fb872dafc434bf60041f78`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short --junitxml=temp/memo-review-fixed-head-full-20261112.xml
```

Observed **1918 passed, 1 warning in 447.33s** with normal Windows GC. The warning
is the intentional duplicate-member ZIP tamper test. No skips, tolerance changes,
timeout inflation or clipboard mocks were introduced. Independent reviewer
`/root/independent_memo_review` accepted the exact source correction and separately
observed **12 archive tests passed in 1.61s**, documentation and diff checks clean.
The documentation-only successor commit retains this exact source/test tree.

An earlier run started with uncommitted production changes and continued while
the fix was committed: **1905 passed, 13 failed, 1 warning in 468.50s**. All thirteen
failures were the Sandbox harness correctly rejecting changed production inputs.
That run is not clean validation. The stable-head rerun above supersedes it.
The unrelated screenshot-rendering integration group also passed **20 in 22.61s**.

Additional observed gates: tracked Ruff lint/format **402 files**, mypy **132 files**,
`scripts/check_docs.py`, `mkdocs build --strict`, `pip check` and `git diff --check`
passed. PR source-head Windows/Ubuntu checks and automated comparison passed;
focused Windows CI was skipped by scope selection, not represented as a pass.

### Post-wake handoff

The historical eleven native UI failures all passed in this full run. This is
current-environment evidence, not eleven production fixes. Continue with explicit
clipboard contention/desktop ownership, constrained-screen RAW sizing, and actual
geometry-settle signals for Difference parity. Preserve existing exact assertions
and reproduce a defect before changing behavior. Do not restore retired presets,
file catalogs, reverse matching, Update or separate Export controls. Session v1
stays unchanged. Physical DPI/multimonitor/SMB/private Enterprise and new human
interaction acceptance are unverified.

Merge is pending at this documentation commit; authoritative merge SHA and handoff
comment will be recorded on PR #227 / Issue #210. The issue must remain open.
Runtime sleep/wake and continuation details are in ignored `temp/agent-power/`;
they are machine-local, not product source. The sleep helper explicitly enables
SeShutdownPrivilege and checks the suspend result. Its privilege-only probe passed
without suspending the computer. Replacement timer and automatic continuation
remain to be registered after the merge.

All agent commits use owner-configured `mc.kang` identity with
`Co-authored-by: ChatGPT <noreply@openai.com>`; owner-authenticated GitHub activity
is marked ChatGPT-assisted. No human commits are rewritten. Existing eleven owner
untracked files remain untouched. All changed files in the review fix are
`src/pixelscope/io/memo_archive.py`, `tests/unit/test_memo_archive.py` and this plan;
the final documentation checkpoint also updates `CURRENT_STATE.md` and
`memo-roi-simplification.md`.

## Bounded eleven-failure verification complete

The owner narrowed the remaining work: check the eleven historical failures,
fix a confirmed error if reproduced, and finish if the cause remains unconfirmed
but a fresh full test run passes. Do not extend this into forced-environment
experiments or indefinite root-cause research.

Verified checkout: merged `main@97a356f0678793c0d6b4eee0064d3837226ddf3b`.
No source/test or HEAD changes occurred during either run.

The exact eleven node IDs were extracted from the historical failure XML and
executed without skips, mocks, changed tolerances or timeout inflation:

```powershell
.\.venv\Scripts\python.exe -c "import subprocess,sys,xml.etree.ElementTree as E; root=E.parse('temp/memo-roi-full-20261109.xml'); nodes=[t.attrib['classname'].replace('.','/')+'.py::'+t.attrib['name'] for t in root.iter('testcase') if t.find('failure') is not None]; assert len(nodes)==11; raise SystemExit(subprocess.call([sys.executable,'-m','pytest','-q','--tb=short','--junitxml=temp/native-eleven-recheck-20261112.xml']+nodes))"
.\.venv\Scripts\python.exe -m pytest -q --tb=short --junitxml=temp/native-eleven-final-full-20261112.xml
```

Observed results, both exit 0:

- Exact historical failures: **11 passed in 8.27s**.
- Normal-GC Windows full suite: **1918 passed, 1 warning in 449.51s**.
- The sole warning is the existing intentional duplicate-ZIP-member tamper test.
- No production error reproduced; no source/test modification was needed. The
  historical root cause remains unconfirmed, rather than claimed repaired.
- No new manual UI/DPI/SMB/packaging/Enterprise acceptance was performed.

**Complete under the owner's stated criterion.** No additional investigation of
these eleven cases or independent review is pending. No new work automation or
power timer was registered: the prior continuation remains PAUSED and the two
recorded sleep/wake tasks were cancelled at the owner's request. PR #227 merged
as `97a356f0`; Issue #210 remains open. Only this plan and `CURRENT_STATE.md` are
updated locally for this verification; no Git commit is created. The Issue #210
completion comment is explicitly ChatGPT-assisted. Existing owner untracked files
remain unchanged.
