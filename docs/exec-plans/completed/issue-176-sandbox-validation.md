# Issue #176 / PR #179 Sandbox validation

Status: Complete for requested B1/B4/C1 scope. Owner: ChatGPT-assisted. Updated: 2026-10-15.

## Goal and scope

Automate B1 interactive No, B4 running Core refusal and C1 installed-payload
failure / exit 77 against the existing installer at implementation `dce97be`.
Do not build, publish, merge, alter release identities or change production checks.
Existing untracked owner files are preserved.

## Evidence and design

The [existing acceptance plan](https://github.com/delphykmc/pixelscope/issues/176#issuecomment-6168224124)
and [B3 evidence](https://github.com/delphykmc/pixelscope/pull/179#issuecomment-6173834193)
are the baseline. B2/B3 are prior evidence, not new runner results.
The checkout is `verify-issue176-m3` at PR HEAD
`dce97be97b70973b7400ecd7b6706e8b74f6ee4f`.

The host runner stages only two existing installers, descriptor and guest script
to a dedicated external run folder. WSB maps inputs read-only and a case-specific
output folder writable. The repository is never mapped. Network and clipboard
are disabled. Each case starts a new Sandbox and ends with guest shutdown;
existing Sandbox sessions cause refusal. Installers execute only in the guest,
after WDAG account, Hyper-V identity and canonical mapped paths are checked.
SHA-256 is checked in host and guest. No host Core registry mutation is permitted.

B1 uses the exact conversion dialog and No button. B4 launches the installed
Core and requires it still running after refusal. C1 uses the actual interactive
Finish-page checkpoint to mutate one installed manifest-owned dependency before
ssDone; inability to reach this checkpoint is BLOCKED, never PASS. This replaces
the older suggested verifier-stub rebuild, preserving immutable release outputs
and the production verifier. Core snapshots, registry, exit code and setup logs
must corroborate every verdict.

## Validation and progress

1. Inspect installer, tests, packaging contracts and existing GitHub evidence.
2. Implement bounded host/guest runner and safety regression tests.
3. Parse PowerShell, run focused tests and docs checks; inspect generated WSB.
4. Execute cases; collect raw results and report actual observations on PR #179.

Known limits: English Inno wizard recognition; standard Yes/No buttons use
language-independent Win32 IDs. Sandbox must support mapped folders
and interactive LogonCommand. C1 proves installed dependency verification failure,
not uninstaller failure, interrupted install or retry. GUI startup and downstream
revision upgrade remain separate acceptance gates. No production source changed.

## Observed progress

- 2026-10-15: Both existing setup files were hashed. Downstream matches the
  owner's exact `30441EC0...D6D56`; Core SHA-256 is
  `135E3775394D077E5A1CC518C2D4D6432244D6E9AE7E97A971D73A8422807303`.
  The existing manifest retains historical build provenance `0cf9c0c`; it was
  not rewritten to the later installer-code HEAD. No payload/revision rebuild.
- Initial prepare found an existing Sandbox. The owner closed it; no existing
  session was terminated by the harness. Actual preparation needed elevated
  tool execution to access the designated external directory.
- First run `20261015-021559-157d3d13ef50413fb3c638ad37b6f090`: B4 PASS,
  exit 1, unchanged Core EXE/registration, Core still running, downstream absent
  and expected process-refusal log. B1/C1 BLOCKED on localized message-box labels.
- Second run `20261015-021848-43c95b3ef802436094be10b6ea69e321`: B1 PASS,
  exit 1, actual `아니요(N)` button ID 7 invoked, unchanged Core, downstream
  absent and expected consent-refusal log. C1 BLOCKED because actual wizard
  caption was `Next`, not `Next >`. No fault injection in this attempt.
- Focused host + existing release-target tests: 46 passed in 17.67s.
  Final host safety tests: 5 passed in 8.65s.
  PowerShell parser, docs, Ruff check/format and diff checks passed.
  No full pytest, packaging tool, publication or merge was executed.
- Third run `20261015-022744-4b6e688bbd244d14b694428b7323c973`: C1 injected
  the installed `_bz2.pyd` fault and observed verifier exit 21 / PARTIAL log;
  BLOCKED because Inno exposed localized OK as ID 2, not Win32 ID 1. Exit 77
  was not inferred. Both interruption records remain in external evidence.
- Final run `20261015-023214-2ac97978612c4599aeef9147988a4d01`: B1 PASS
  again with final click mechanism; C1 PASS with actual process exit 77,
  identical Core EXE/registration, downstream version/registry 0.1.0.1,
  verifier exit 21, PARTIAL log and acknowledged warning. Process-scoped UIA
  discovers controls; asynchronous BM_CLICK handles modal completion safely.
  The exact warning text gates localized OK IDs 1/2. No production bug observed
  in these three requested cases. See [result report](../../issue-176-sandbox-results.md).
