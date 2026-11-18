# Issue #176 / PR #179 merge readiness

Status: Shared acceptance and local merge-readiness validation complete.
Owner: ChatGPT-assisted. Updated: 2026-10-15.
Final PR CI and merge outcome are tracked in PR #179.

## Goal and authorization

The owner authorized detailed GitHub evidence and requested completion of necessary
remaining validation followed by merge if all required conditions are satisfied.
Preserve the previous B1/B4/C1 evidence and existing host-isolation requirements.
No production payload, release revision, manifest or integrity gate changes.

## Remaining evidence

The latest review has no remaining confirmed code P1, and all three CI workflows
at `dce97be` pass. However its explicit pre-merge list includes Core-uninstaller
failure and interruption/retry. Add fresh Sandbox cases for those paths plus
fresh downstream/reinstall/GUI smoke, stale identity refusal and missing dependency.
Record settings/file sentinel preservation and HKCU32/HKCU64 alias visibility.
Do not label revision 1 reinstall as a revision upgrade. D7 separately tests the
public fixture's real cross-revision upgrade; PRIVATE SUB qualification remains
downstream release ownership.

## Delivery and checks

Retain reusable host/guest scripts and docs in the PR. Move the subprocess-backed
harness tests to `tests/integration` per `docs/QUALITY.md`. Run local applicable
release and harness tests, broad Ruff/mypy/docs/pip/diff checks. Review full PR
diff and documentation deletion scope; commit only intended files with ChatGPT
co-author attribution, push to the existing PR branch, wait for final CI, update
review disposition and PR description. Merge only if the final checks permit it;
do not bypass a newly discovered defect or unmet required gate.

## New cases

- D1: exclusive lock on guest-owned registered Core uninstaller, complete intact
  downstream install, observe exit 77, release lock, consented repair/retry.
- D2: terminate only the observed installer process tree at its installed Finish
  checkpoint, establish preserved Core, then retry same immutable installer.
- D3: fresh downstream install without Core, same-version reinstall and real GUI
  window/normal-close smoke.
- D4: stale Core InstallLocation in guest HKCU, verify preflight refusal, restore
  exact field, then consented retry including alias/state checks.
- D5: missing installed dependency at Finish, exit 77 with Core retained, then
  rerun original immutable setup to repair and convert.
- D6: lock guest-owned uninstaller `.dat`, require actual uninstaller nonzero
  return (not merely launch failure), setup 77, unlock and retry.
- D7: separately build immutable revision 2 using pinned PyInstaller/Inno and the
  existing fixture AppId; install revision 1 then upgrade to 0.1.0.2 in Sandbox.
- D8/D9: corrupt installed manifest/EXE at Finish, require compiled-hash refusal
  before Core removal. For a corrupt EXE, also preserve the silent unknown-version
  refusal and restore the exact original guest backup before consented repair.

Known limit: these tests cannot claim arbitrary interruption timing coverage or
PRIVATE SUB production acceptance. Deterministic checkpoints are recorded exactly.

## Progress

- Initial extended D1-D5: all PASS, including retry exit 0, fresh install/reinstall
  and actual downstream GUI window/normal close exit 0. State sentinels survived.
- Preserved all eight original Core/revision-1 release artifacts by hash and
  backed up revision-1 onedir. Built separate revision 2 (Python 3.10.11,
  PyInstaller 5.7.0, supported Inno); real EXE FileVersion/ProductVersion 0.1.0.2
  and release bundle PASS. Revision-2 setup SHA-256:
  `A11DBEBE759FD10A6E84EB1EBD589820E3C71F2B78AD28303D88392436C7BE2A`.
- Release-focused tests: 58 passed in 2.08s. Harness integration tests: 13 passed
  in 30.83s before the final manifest/EXE-case additions.
- Broad Ruff invocation identified only the owner's three existing untracked GC
  diagnostic scripts. All tracked Python plus the delivered harness linted and
  formatted cleanly (338 files). mypy: 106 source files PASS; pip check PASS.
- Restricted full pytest encountered temporary `.git/config` permissions and
  INI settings behavior. Exact Git tests passed 2/2 and exact Plots clamp test
  passed 1/1 under normal permissions. Verified only this run's exact pytest PIDs
  before terminating it; normal-permission full suite is running without changed
  assertions, skips, disabled GC or widened timeouts. This is a local gate, not CI.
- D1-D9 all PASS. Actual Core-uninstaller error 1 produced setup 77; retry 0.
  Actual revision 1 -> 2 upgrade returned 0 with full installed payload validation.
  Manifest and EXE compiled-hash failures returned 77 and recovered safely;
  corrupt EXE silent retry refused with 1 before exact guest-backup restoration.
- First normal full run: 1426 passed / 2 failed, both synthetic screenshot tests
  inheriting the outer offscreen selection. Explicitly isolated those two mocked
  native contracts with `monkeypatch.setenv`; production capture guard and every
  assertion remained unchanged. Focused screenshot contracts: 23 passed in 2.33s.
- Final normal-permission Windows/offscreen automatic-GC full pytest:
  **1428 passed in 369.86s (6:09)**. No package/runtime source changes were needed.
  Integration harness tests live under `tests/integration`, not durable unit CI.
- Prepared owner-identity Git delivery with explicit ChatGPT co-author trailer.
  Existing human commits and owner untracked files are preserved. Final CI and
  exact merge disposition are external PR records, not presumed by this plan.
