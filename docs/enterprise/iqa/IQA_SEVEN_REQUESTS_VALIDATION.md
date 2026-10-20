# Seven-request final local validation and Handoff preparation

Status: Native Hover test failure resolved by the focused follow-up below; other
Handoff acceptance remains incomplete. The recorded full regression is historical.
Owner: ChatGPT-assisted validation, 2026-10-21.

## Scope and baseline

Validate the already-integrated seven requests as one branch. Do not merge the
original PRs again, merge Handoff, modify PUBLIC main, build packages, or add a
portable codec/provider. Preserve scientific values, valid masks, ROI statistics
and export schemas. Keep changes under Enterprise IQA ownership.

- Integration input: `2da9d9ec404a99cadc8f276a56d2b78bc79b82ba`.
- Handoff and merge-base: `8420be534ac877f8440a2e93766e3da9f8d48728`.
- PUBLIC main observed: `3805eba7dc4b03833b762f127bfafd0acadf5134`.
- Root checkout remains on main with all original user untracked files preserved.
  Validation uses the repository-local `temp/iqa-seven-validation` worktree.
- Original PRs: [#200](https://github.com/delphykmc/pixelscope/pull/200),
  [#196](https://github.com/delphykmc/pixelscope/pull/196),
  [#195](https://github.com/delphykmc/pixelscope/pull/195),
  [#198](https://github.com/delphykmc/pixelscope/pull/198),
  [#197](https://github.com/delphykmc/pixelscope/pull/197),
  [#201](https://github.com/delphykmc/pixelscope/pull/201),
  [#199](https://github.com/delphykmc/pixelscope/pull/199).

## Execution sequence and corrections

1. Inspect status, local/remote heads, ancestry, ownership and existing environment.
2. Run Ruff check/format, mypy, documentation and dependency checks.
3. Run AnalysisWindow, explicit open/save error contracts, all Enterprise IQA tests,
   then full local pytest with normal automatic GC.
4. Check whitespace and Handoff diff; inspect actual native Windows GUI.
5. Prepare a single integration PR only when automated gates pass; preserve any
   outstanding visual acceptance as explicit review blockers. Never merge it here.
6. Check resulting GitHub Actions and report exact evidence and attribution.

The input failed Ruff import sorting/line length and had trailing blank lines in
`test_analysis_window.py`; only formatting was corrected. The owner's explicit
Dark Neutral RGB `(94, 94, 94)` differs from both the input and original #198
`(94, 104, 115)`. A literal-RGB combined regression first failed (1 failed,
1 deselected in 0.75s), then the shared palette, exact tests and owning docs were
corrected. This changes neutral visual PNG pixels consistently with the requested
palette; signed numbers, masks, statistics and export schemas do not change.
Quality-mode toggling remains independent of export data.

## Environment and evidence

Windows CPython 3.10.11 x64, PySide6/Qt 6.4.2, pytest 7.4.4. Existing root `.venv`
was reused. `PYTHONPATH` points exclusively to this worktree's `src` for source
resolution. Automated Qt tests use `QT_QPA_PLATFORM=offscreen`; actual GUI checks
use `windows`. Packaging tools were neither installed nor run.

Logs/XML and temporary synthetic fixtures remain local under
`temp/iqa-seven-evidence`; they are not architecture or committed artifacts.

An initial sandbox Enterprise run produced **192 passed, 19 failed, 4 skipped in
56.32s**. Atomic rename and QSettings writes were denied by the Windows sandbox.
The same environment outside that restriction passed **211/0/4 in 54.74s** before
the palette correction. The sandbox full run and pre-correction unrestricted full
run were interrupted and are not full-suite evidence. Corrected-environment final results are recorded below.

## Native visual checks and remaining acceptance

Actually observed at the original palette: real 3840x2160 synthetic A/B images,
three-pane rendering, A/B swap and stable title/source identity, synchronized
crosshair coordinates/RGB/map readout, maximize/restore, Quality Verdict and
Reference Tint composition, Ctrl+W returning to an empty window, and 150% Qt scale
basic layout. A separate role fixture confirmed Reference/Target title and
middle-elided long captions, and closing the second result displayed the first.
This is partial native visual evidence, not completion of the entire requested
Windows matrix. Palette correction is separately covered by exact RGB regressions.

Owner visual checklist before merge:

- [ ] Repeat final-palette 4K resize/hover/overlay, role swap and splitter checks.
- [ ] Verify long readout elision/full tooltip and Unknown Signal Level tooltip.
- [ ] Exercise native Open/Save dialogs with the real injected `.pxiqa` adapter:
  filter, suggested name, automatic suffix, success, expected/unexpected failure,
  preserved result, bounded/private error text and no false success message.
- [ ] Move hover after each I/O error; verify the error survives and permanent
  readout geometry stays fixed. Verify close/Exit leaves host files/jobs unchanged.
- [ ] Repeat multiple-result open/close and Exit with the host window present.
- [ ] Repeat normal/high DPI, including mixed-DPI monitor movement and small
  usable window sizes. A forced 150% process scale does not prove mixed-DPI behavior.

The local extra GUI fixture has synthetic callback handlers only; it does not
implement or qualify a real portable result format.

## Attribution

Use configured owner Git author/committer with
`Co-authored-by: ChatGPT <noreply@openai.com>` on new commits. GitHub CLI uses
`delphykmc`; any PR body is explicitly ChatGPT-assisted. Existing commits are not
rewritten. No PUBLIC main or Handoff merge is authorized in this task.

## Observed automated results on corrected code

All commands use the root `.venv/Scripts/python.exe` from this worktree, with
`PYTHONPATH=<worktree>/src`. Pytest durations below are the pytest summaries,
not the parent launcher time.

| Command / selection | Passed | Failed | Skipped | Seconds |
|---|---:|---:|---:|---:|
| `-m pytest -q -ra tests/enterprise/iqa/test_analysis_window.py` | 23 | 0 | 0 | 13.96 |
| Same module, `-k 'test_result_file_callback_errors_are_safe_and_bounded or test_contributed_result_file_type_keeps_callback_errors_safe' -vv` | 4 | 0 | 0 | 1.11 |
| `-m pytest -q -ra tests/enterprise/iqa/` | 211 | 0 | 4 | 55.65 |
| First complete `-m pytest -q -ra` with global offscreen and no public pin | 1601 | 3 | 4 | 437.12 |
| Corrected-environment ownership + screenshot modules | 42 | 0 | 0 | 14.66 |
| Corrected-environment complete suite (all tests selected) | 1604 | 0 | 4 | 429.26 |
| Additional native `windows` UI selection (five modules) | 21 | 1 | 0 | 10.68 |
| Isolated unchanged native hover test, unrestricted | 0 | 1 | 0 | 1.78 |
| Isolated unchanged native hover test, sandbox | 0 | 1 | 0 | 1.94 |

The four explicit callback cases were individually observed PASS:

- `test_result_file_callback_errors_are_safe_and_bounded[open]`
- `test_result_file_callback_errors_are_safe_and_bounded[save]`
- `test_contributed_result_file_type_keeps_callback_errors_safe[open]`
- `test_contributed_result_file_type_keeps_callback_errors_safe[save]`

No selected callback case skipped. The four suite skips already exist at Handoff:
symlink privilege, real-Git transfer opt-in, real MainWindow U6 opt-in, and E2B
ancestry opt-in. No new skip/deselection/xfail was introduced.

Static commands observed after the RGB correction: `-m ruff check .` (exit 0,
0.42s), `-m ruff format --check .` (387 files, exit 0, 0.38s), `-m mypy src`
(124 source files, exit 0, 5.89s), `scripts/check_docs.py` (contract passed,
0.75s), `-m pip check` (no broken requirements, 1.47s). `git diff --check`
against Handoff and `origin/main` passed after the formatting correction.

### Full-suite environment correction

The three full-suite failures were test-environment preconditions:

1. `test_enterprise_reserved_paths_are_not_owned_by_main` requires the approved
   ancestor `PIXELSCOPE_PUBLIC_MAIN_SHA=3bef0880add2019d62f783d717eb1be518144e19`
   on this Handoff checkout, as documented in
   [E2B MAIN sync](IQA_UX3E_E2B_MAIN_SYNC.md). Current PUBLIC main is newer and
   must not be substituted for the verified Handoff ancestor.
2. `test_failed_native_child_is_capture_failed_not_changed` and
   `test_new_real_scene_uses_pinned_manifest_geometry_through_e1_validator`
   correctly reject the inherited `QT_QPA_PLATFORM=offscreen` before invoking
   their mocked native screenshot child. The final launcher removes that global
   variable and constructs `QApplication(['pytest', '-platform', 'offscreen'])`
   before calling `pytest.main(['-q', '-ra', ...])`. UI tests retain offscreen
   rendering while the screenshot environment contract retains its actual
   meaning. All tests remain selected, assertions unchanged, automatic GC on.

### Initial native gate (Hover resolution recorded below)

The unchanged test
`test_hover_links_three_guides_and_reads_rgb_and_masked_map` sees
`_hovered_pixel is None` immediately after `qtbot.mouseMove` on the native
Windows platform. It reproduces in isolation with and without sandboxing.
The additional 22-test run also printed Windows COM exception `0x8001010d`
while processing events in the file-menu hover test; that test subsequently
passed, but this diagnostic is not suppressed or treated as a clean native run.

Diagnostic experiments with normal event-driven waiting and explicit activation
did not resolve the hover failure. Those test edits were discarded, including
one intermediate diagnostic run with a missing import. No product change,
assertion weakening, timeout inflation, skip or exception suppression was kept.
A standalone native probe reported exposed/active windows but QTest moves did
not advance the OS cursor across the three requested viewport coordinates.
This suggests an input-delivery limitation in this execution context; it does
not establish a product cause. Real UI pointer interaction did display shared
guides/readouts, but owner-native reproduction and COM review remain required.

Native selection: `test_analysis_file_menu_request7.py`,
`test_analysis_hover_status.py`, `test_analysis_usability_request3.py`,
`test_analysis_integration_req1_req2_req3_req4.py`, and
`test_quality_presentation_window.py` under `tests/enterprise/iqa/`.

### Contract evidence map

- Source/title/roles/resize/guide identity: request-3 usability plus combined
  request 1/3/4 and 1/2/3/4 tests.
- Quality opt-in/direction/threshold/trusted gate, neutral and science/export
  invariants: quality presentation pure/window and combined policy/tint tests.
- Fixed readout geometry/elision/full tooltip/unknown signal and transient
  status independence: analysis hover-status and request-7 hover tests.
- Close/next/empty/Exit/job-file independence, contributed type/filter/suffix,
  safe callbacks: request-7 file-menu plus the four explicit callback cases.


## Final outcome and Handoff gate

The corrected-environment complete suite finished **1604 passed, 0 failed,
4 skipped in 429.26s** with normal automatic GC. This validates production code
commit `61c992bdafa20d055bccc12661cf0f0b0c2f0f07`; subsequent changes only add this
record and its Handoff navigation link. Full-suite stdout/XML are
`temp/iqa-seven-evidence/pinned-full.log` and `pinned-full.xml`.

The initial input had 29 changed Enterprise files (+3654/-89), with 15 reachable
commits above Handoff. The task adds the narrow correction commit and an evidence
commit; the final change set has 30 files, all under reserved Enterprise IQA roots.
No unexpected durable-document contraction occurred. Root main and user untracked
files remain preserved. Handoff stays at the requested base; no original PR was
merged individually and no existing commit was rewritten.

At corrected code HEAD, both Actions completed successfully:
[Change-scoped validation](https://github.com/delphykmc/pixelscope/actions/runs/39462773876)
and [User Guide validation](https://github.com/delphykmc/pixelscope/actions/runs/39462773875).
The first includes successful classifier, cheap validation and source typecheck;
Focused Windows is policy-skipped. Hosted full pytest was not added or run.
A final documentation-only push is checked separately and reported in the chat.

**Verdict: BLOCKED.** The native UI selection is not clean, and the complete
manual matrix is not qualified. The user's PR creation instruction is conditional
on satisfying acceptance, so no integration PR is created and no merge is made.
No same-head integration PR existed in the initial lookup. A local proposed PR
body is retained in `temp/iqa-seven-evidence/INTEGRATION_PR_BODY.md`; after native
closure, recheck remote heads and existing PRs, create one PR targeting
`handoff/enterprise-iqa-window`, verify its Actions, and obtain owner review.

The owner must resolve/reproduce native Hover and the COM diagnostic, complete
the unchecked visual checklist above, then approve Handoff integration. A true
portable `.pxiqa` codec and private provider qualification remain outside this
public-safe window task. Do not interpret a development Handoff merge as approved
PRIVATE SUB transfer.

## Handoff file inventory

- `docs/enterprise/iqa/IQA_QUALITY_PRESENTATION.md`
- `docs/enterprise/iqa/IQA_REQUEST7_FILE_MENU.md`
- `docs/enterprise/iqa/IQA_SEVEN_REQUESTS_VALIDATION.md`
- `docs/enterprise/iqa/IQA_UX1.md`
- `docs/enterprise/iqa/IQA_UX2.md`
- `docs/enterprise/iqa/IQA_WINDOW_HANDOFF.md`
- `src/pixelscope_enterprise/iqa/analysis_model.py`
- `src/pixelscope_enterprise/iqa/analysis_window.py`
- `src/pixelscope_enterprise/iqa/attribute_chart.py`
- `src/pixelscope_enterprise/iqa/composition.py`
- `src/pixelscope_enterprise/iqa/demo.py`
- `src/pixelscope_enterprise/iqa/hover_fields.py`
- `src/pixelscope_enterprise/iqa/hover_status.py`
- `src/pixelscope_enterprise/iqa/insights.py`
- `src/pixelscope_enterprise/iqa/quality_presentation.py`
- `src/pixelscope_enterprise/iqa/spatial_dock.py`
- `tests/enterprise/iqa/test_analysis_file_menu_request7.py`
- `tests/enterprise/iqa/test_analysis_hover_status.py`
- `tests/enterprise/iqa/test_analysis_insights.py`
- `tests/enterprise/iqa/test_analysis_integration_req1_req2_req3_req4.py`
- `tests/enterprise/iqa/test_analysis_integration_req1_req3.py`
- `tests/enterprise/iqa/test_analysis_integration_req1_req3_req4.py`
- `tests/enterprise/iqa/test_analysis_model.py`
- `tests/enterprise/iqa/test_analysis_usability_request3.py`
- `tests/enterprise/iqa/test_analysis_ux1.py`
- `tests/enterprise/iqa/test_analysis_ux2a.py`
- `tests/enterprise/iqa/test_analysis_ux2c.py`
- `tests/enterprise/iqa/test_analysis_window.py`
- `tests/enterprise/iqa/test_quality_presentation.py`
- `tests/enterprise/iqa/test_quality_presentation_window.py`


## Focused native Hover follow-up (2026-10-21)

Owner scope clarification: diagnose and fix the native Hover test only; exclude
actual `.pxiqa` reader/writer qualification and do not rerun the full repository
suite. No production source or reader/writer callback changes are part of this
follow-up. PUBLIC main and Handoff remain unchanged.

### Observable diagnosis

The same shown Windows Qt window was observed through an application event filter:

- `QTest.mouseMove(QWidget)` produced no viewport `MouseMove` events and the OS
  cursor did not move in this execution context. `_hovered_pixel` stayed `None`.
- `QTest.mouseMove(QWindow)` with viewport-to-window coordinate mapping produced
  a `MouseMove` at each of the three viewport receivers. All three yielded
  source pixel `(16,16)` and the original RGB/map/guide assertions passed.
- This distinction matches the [Qt 6.4.2 QTest implementation](https://github.com/qt/qtbase/blob/v6.4.2/src/testlib/qtestmouse.h):
  the unpressed QWidget branch relies on `QCursor::setPos`; the QWindow overload
  synthesizes QPA input, including normal Qt hit testing and view event handling.
  QWindow test input bypasses the OS platform injection layer, so it is not alone
  evidence of a physical mouse working.
- A real 4K Windows fixture was separately exercised using the Computer Use
  plugin. All three viewports received `buttons=0`, `spontaneous=true` native
  pointer moves; the source coordinates, Reference/Target RGB, raw signed map and
  all three visible guide positions updated together. Example source coordinates
  were Map `(2148,902)`, Target `(1572,1214)` and Reference `(1961,1525)`.
  Readout/guide snapshots were recorded after the actual handler signal.

Conclusion: the reproduced assertion failure is the QWidget test input delivery
path, not a demonstrated Hover feature defect. Fix only
`tests/enterprise/iqa/test_analysis_usability_request3.py`: send QWindow test
input in the proper window coordinate system and attach a `QSignalSpy` to each
view's `pixel_hovered` signal. Require a delivery from that receiver and its exact
`[16,16]` payload before the existing state, RGB, map and three-guide assertions.
This also prevents a stale state from a previous view falsely satisfying the test.
No direct call to the production hover handler replaces the failing mouse move.
No timeout, assertion weakening, skip, GC or exception suppression was added.

### Focused validation observed

Windows CPython 3.10.11 x64 / PySide6 6.4.2, normal automatic GC, existing `.venv`:

| Selection / platform | Passed | Failed | Skipped | Seconds |
|---|---:|---:|---:|---:|
| Corrected original Hover test / `windows` | 1 | 0 | 0 | 1.39 |
| Same five-module native selection, run 1 | 22 | 0 | 0 | 8.67 |
| Same selection / `windows`, run 2 | 22 | 0 | 0 | 9.67 |
| Same selection / `windows`, run 3 | 22 | 0 | 0 | 9.64 |
| Same selection / `offscreen` | 22 | 0 | 0 | 7.39 |

Commands used `python -m pytest -q -ra` with the five modules listed in the
native selection above. Native settings were `PYTHONPATH=<worktree>/src` and
`QT_QPA_PLATFORM=windows`; only the final comparison used `offscreen`.
Logs/XML are `native-ui-qwindow.*` and `hover-focused-{windows-2,windows-3,offscreen-1}.*`
under `temp/iqa-seven-evidence`. Event-path diagnostics are `hover-events.log`;
physical pointer observations are `physical-hover.jsonl`. These local synthetic
probes are not shipped as production architecture.

### COM diagnostic distinguished from the Hover assertion

The `0x8001010d` message did not occur in native run 1, but occurred in runs 2/3
while all 22 tests still passed with process exit 0. It was not suppressed.
A read-only vectored exception observer, which always returned CONTINUE_SEARCH,
recorded `qwindows.dll / Qt6Gui.dll -> UIAutomationCore.dll -> combase/RPCRT4`
at the exception. A minimal `QMainWindow/QGraphicsView` test with **no PixelScope
imports** reproduced the same diagnostic and passed (1 test, 0.45s).
[Microsoft documents the code](https://learn.microsoft.com/en-us/windows/win32/com/com-error-codes-3)
as `RPC_E_CANTCALLOUT_ININPUTSYNCCALL`, an outgoing COM call made while dispatching
an input-synchronous call. The stack and baseline isolate this occurrence to the
Windows Qt accessibility/COM path; they do not prove which external accessibility
client caused it or qualify that diagnostic as fixed. No evidence justified a
PixelScope ownership/lifecycle workaround, disabling accessibility, suppressing
faulthandler, or changing the pinned Qt dependency.

The Hover test gate is resolved. The COM diagnostic remains transparently recorded
as a separate Qt/Windows accessibility limitation. Actual `.pxiqa` adapter work
was explicitly excluded by the owner, and experimental callback-test edits were
removed. No new full-suite PASS or completion of the remaining GUI matrix is claimed.
