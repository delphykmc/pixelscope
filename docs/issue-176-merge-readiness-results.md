# PR #179 merge-readiness follow-up — 2026-10-15

Shared Windows acceptance and local repository validation: PASS.
Final PR HEAD CI and actual merge disposition are tracked in
[PR #179](https://github.com/delphykmc/pixelscope/pull/179).

The owner authorized detailed PR evidence and requested remaining necessary work
followed by merge once mandatory conditions pass. The earlier
[B1/B4/C1 report](issue-176-sandbox-results.md) remains the initial record.
Production installer implementation remains `dce97be`; new repository changes
are the acceptance harness, its tests and documentation.

## Additional isolated Windows evidence

| Case | Observed result | Recovery / additional check |
| --- | --- | --- |
| D1 Core uninstaller launch blocked by exclusive EXE lock | PASS, setup 77, Win32 launch code 32, Core retained | Unlock; retry 0, Core removed, complete downstream payload |
| D2 installer terminated at installed Finish checkpoint before ssDone | PASS, terminated setup -1, Core retained | Original immutable setup retry 0 |
| D3 no-Core fresh install, same-version reinstall, downstream GUI | PASS, setup/reinstall 0; actual PixelScope window, normal close/exit 0 | Full payload verification after each setup |
| D4 stale Core InstallLocation | PASS, setup 1, no downstream mutation | Restore exact registration field; retry 0 |
| D5 missing installed dependency | PASS, setup 77; Core retained | Original setup repairs dependency; retry 0 |
| D6 actual Core uninstaller error (exclusive `.dat` lock) | PASS, actual uninstaller 1, setup 77; Core retained | Unlock; retry 0 |
| D7 same-AppId revision 1 to separately built revision 2 | PASS, both setup exits 0 | Full installed 0.1.0.2 payload; unchanged uninstall identity |
| D8 corrupt installed manifest | PASS, setup 77; Core retained | Original setup repair/retry 0 |
| D9 corrupt installed EXE | PASS, setup 77; Core retained | Silent unknown-version retry 1; restore exact guest backup; retry 0 |

Core HKCU32/HKCU64 alias visibility is captured in snapshots. Settings-registry
and application-data file sentinels survived the passing cases. This is explicit
sentinel coverage, not a claim to exercise every user preference or file.
Failure/retry snapshots retain `AfterFirstAttempt`, `AfterRetry` and final state.

Raw output parent remains the dedicated external `PixelScopeSandbox` folder from
the initial report. D3 is in run `20261015-071004-51fb0e8f64d046929a244b428f34932f`.
D1/D2/D4/D5/D6/D7 final snapshots are in
`20261015-071759-3356e247afba46939655910464a8d446`.
D8/D9 are in `20261015-072715-d6da551700e548408635614834d12d99`.

## Immutable revision build

Python 3.10.11, pinned PyInstaller 5.7.0 and supported Inno 6 compiled a separate
revision-2 fixture using the unchanged public source/spec and the same disposable
AppId. Existing eight Core/revision-1 release artifacts were recorded by SHA-256
before building and all eight remained unchanged afterward. Revision 1 was never
rebuilt or overwritten. The original revision-1 onedir was backed up, restored
after the revision-2 build, and every original manifest-owned file was verified.
The revision-2 onedir is retained separately under ignored build output.

Revision-2 setup SHA-256:
`A11DBEBE759FD10A6E84EB1EBD589820E3C71F2B78AD28303D88392436C7BE2A`.
Its actual EXE FileVersion/ProductVersion are `0.1.0.2`; canonical portable,
installer and bundle commands passed. The new manifest records the build's
`dce97be` downstream source and existing public-main baseline. No provenance
rewrite, same-revision payload change or integrity weakening occurred.

Commands (using `.venv-release/Scripts/python.exe`):

```text
scripts/build_release.py --target-descriptor build/sandbox-fixtures/issue176-revision2.json
scripts/build_portable_release.py --target-descriptor build/sandbox-fixtures/issue176-revision2.json
scripts/build_installer_release.py --target-descriptor build/sandbox-fixtures/issue176-revision2.json --iscc <supported ISCC>
scripts/validate_release_bundle.py --target-descriptor build/sandbox-fixtures/issue176-revision2.json
```

## Repository validation and review disposition

- Release-target + original harness selection: 46 passed in 16.18s.
- Release distribution/packaging/candidate/publication selection: 58 passed in 2.08s.
- Final harness integration tests: 15 passed in 31.68s.
- PowerShell parser: host and guest PASS.
- All tracked Python plus the delivered harness: Ruff check and format PASS,
  338 files already formatted. Unrelated owner GC diagnostic scripts remain
  untracked/unmodified; broad `ruff .` identified four existing lint findings
  and three formatting findings in those files only.
- mypy: 106 source files PASS. pip check: no broken requirements.
- Initial restricted full pytest encountered `.git/config` write denial and
  settings behavior from the tool sandbox. Exact Git tests passed 2/2 and exact
  Plots test passed 1/1 with normal permissions. That restricted run was stopped
  after verifying its exact PIDs/command/start time; it is not claimed as PASS.
- First normal-permission Windows/offscreen full pytest: 1426 passed, 2 failed
  in 436.35s. Both failures were screenshot synthetic-child unit tests inheriting
  the enclosing offscreen flag and returning before their mocked subprocess.
  Those two tests now explicitly select a native backend for their synthetic
  contract; the separate offscreen rejection test and production capture guard
  remain unchanged. Focused screenshot contracts then passed 23/23 in 2.33s.
  No assertions, timeout changes, GC suppression or skip additions were used.
- Final normal-permission Windows/offscreen automatic-GC full pytest:
  **1428 passed in 369.86s (6:09)**, command `python -m pytest -q` with
  `QT_QPA_PLATFORM=offscreen`, using the existing CPython 3.10 development venv.

All original code-review threads are resolved; the last review found no remaining
confirmed code P1 and required actual Windows failure/recovery evidence. The
observed matrix now closes the shared conversion's consent, readiness, uninstall
failure, interruption/retry and distribution-upgrade validation gates. The final
owner-authorized merge is conditional on CI at the newly delivered PR HEAD.
No production runtime change was introduced by this validation follow-up.

## Delivered files and attribution

- `scripts/sandbox-runner.ps1`, `scripts/sandbox-guest.ps1`: guarded HOST/guest
  orchestration, case-specific fresh WSB, fault/checkpoint/repair tests and reports.
- `tests/integration/test_sandbox_runner.py`: 15 subprocess-backed preparation,
  isolation and pinning tests; no Installer or Sandbox execution from pytest.
- `tests/unit/test_ui_screenshot_diff.py`: isolate two mocked native captures from
  an enclosing offscreen backend; preserve production rejection and assertions.
- `docs/issue-176-sandbox-runner.md`, `docs/issue-176-sandbox-results.md`, this
  follow-up, both completed execution plans, the packaging opt-in guide and docs
  index: reusable instructions, cumulative evidence and source-of-truth links.

Git delivery uses the observed owner GitHub identity `delphykmc` with its GitHub
noreply address and `Co-authored-by: ChatGPT <noreply@openai.com>`; GitHub records
are explicitly ChatGPT-assisted. No existing human commits are rewritten. Actual
commit identity, final CI and merge result are retained in the PR history.
Owner GC diagnostics and generated original fixture descriptor/spec remain
untracked and untouched. No full pytest group was added to CI.

## Remaining scope limits

D2 exercises interruption between completed edition installation and Core removal,
matching the shared packaging acceptance matrix. Arbitrary mid-copy/power-loss
timing, every possible setting, unusual corporate security policies and actual
PRIVATE SUB production packaging/signing/approval remain release-owner work.
These limits do not replace the observed shared conversion lifecycle results.
No HOST-installed Core has been executed, installed, removed or modified by the
harness; installer runs, fault injection and process termination are guest-only.
