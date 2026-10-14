# PR #179 Windows Sandbox runner

This local acceptance harness exercises the existing conversion-enabled installer;
it does not build or alter release artifacts. The implementation under test defaults
to `dce97be97b70973b7400ecd7b6706e8b74f6ee4f`. The default fixture is the
owner's existing `issue176-vm.json`, `PixelScopeTestEdition` revision 1 with
AppId `{A6C3E629-46AC-4061-841B-46F61ECD0AB3}`. These owner-generated inputs
are not introduced as permanent production packaging configuration.

## Run

Close existing Sandbox sessions first. In a local PowerShell at repository root:

```powershell
.\scripts\sandbox-runner.ps1 -PrepareOnly
# Inspect the emitted .wsb files, then execute:
.\scripts\sandbox-runner.ps1
# Retry an individual case in another clean Sandbox:
.\scripts\sandbox-runner.ps1 -Cases C1
# Additional failure/repair and fresh install cases:
.\scripts\sandbox-runner.ps1 -Cases @('D1','D2','D3','D4','D5','D6','D8','D9')
# Revision upgrade needs a separately built, independently hashed revision 2:
.\scripts\sandbox-runner.ps1 -Cases D7 -UpgradeInstaller <revision-2-setup.exe> -ExpectedUpgradeSha256 <sha256>
```

The runner defaults to a unique run folder below
`C:\Users\Public\Documents\ESTsoft\CreatorTemp\PixelScopeSandbox`.
`-OutputParent` can select a dedicated external output parent. Repository paths,
repository ancestors and reparse paths are rejected. The two existing installers
are staged into a separate input directory; only that directory is mapped
read-only. Each case's empty output directory is the only writable mapping.
The repository, host AppData and host registry are never mapped.
Networking and clipboard redirection are disabled. See Microsoft's
[WSB configuration documentation](https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file).

Host checks pin the reviewed implementation baseline, downstream SHA-256 and
disposable fixture identity. Harness/docs-only descendant commits are permitted
only when tracked production inputs remain identical to the reviewed baseline;
changed production inputs, including uncommitted changes, are rejected.
The guest independently checks both installer digests and refuses execution
unless its WDAG account, Microsoft virtual-machine identity and canonical
mapped script location are established. Host code launches only WindowsSandbox;
installer execution, UI automation, fault injection and shutdown reside in the
guarded guest script. Existing sessions are never force-terminated. A case that
cannot complete or close prevents reuse of its instance for subsequent cases.

After a different implementation or fixture is deliberately reviewed, update
`-ExpectedHead` and `-ExpectedDownstreamSha256`; these parameters do not rebuild
or authorize publishing artifacts. The current fixture layout/version remains
explicitly restricted in the harness. Preserve immutable release inventory and
increment `release_revision` for changed release payloads through the normal
pipeline. Never rewrite a manifest to force a match.

## Contracts and evidence

| Case | Trigger | Required evidence |
| --- | --- | --- |
| B1 | Recognized conversion dialog, Win32 IDNO=7 | Nonzero exit; identical Core EXE hash/version and registration; downstream absent; no-consent log |
| B4 | Actual installed Core running, silent explicit consent | Nonzero exit; identical Core identity; Core still running; downstream absent; process-refusal log |
| C1 | Interactive consent, installed-payload fault at Finish page | Exit 77; Core retained; downstream EXE/registration present; verifier-failure and PARTIAL logs |
| D1 | Exclusive lock on registered guest Core uninstaller | Exit 77 before removal, intact downstream; unlock and retry succeeds |
| D2 | Terminate observed installer tree at installed Finish checkpoint | Core retained; original immutable setup retry succeeds |
| D3 | No Core; fresh downstream, same-version reinstall and GUI normal-close | Both setup exits 0, complete payload and actual GUI window/clean exit |
| D4 | Stale guest Core InstallLocation, then restore exact field | Preflight refuses with no downstream; restored identity retry succeeds |
| D5 | Delete installed dependency at Finish | Exit 77 and Core preserved; reinstall repairs dependency and converts |
| D6 | Exclusive lock on registered guest Core uninstaller data | Actual uninstaller returns nonzero, setup 77; unlock and retry succeeds |
| D7 | Revision 1 to independently built revision 2, same AppId | Both setups 0; full payload verifies at 0.1.0.2; registration identity unchanged |
| D8 | Corrupt guest-installed manifest at Finish | Compiled-hash gate refuses, exit 77; original setup repair/retry succeeds |
| D9 | Corrupt guest-installed EXE at Finish | Exit 77; silent unknown-version repair refuses; restore exact guest backup and retry succeeds |

`result.json` collects exit code, before/after EXE SHA-256 and versions,
HKCU64 uninstall `DisplayName`, `DisplayVersion`, `InstallLocation`, and
`UninstallString`, UI actions, fault evidence and OS version. `core-install.log`,
`downstream-install.log`, `guest.log` and `last-ui.json` provide diagnostics.
Failure/repair cases preserve `AfterFirstAttempt` separately from `AfterRetry`
and the final snapshot. Core registry alias views and settings/file sentinels
provide explicit scope-limited user-state evidence. Retry and upgrade logs are
retained separately from the initial setup log.
The host writes `summary.json` and `report.md`. Results are written before
guest shutdown; verdicts distinguish PASS, FAIL, BLOCKED and NOT RUN.

C1 never replaces the production verifier. It requires the actual Finish
button plus `Installation process succeeded` in the installer log, with no
conversion-completion/partial log yet. It verifies `_bz2.pyd` against the installed
manifest, changes that installed guest-only file, then continues Finish. The
original manifest, EXE and host setup bytes stay intact. If this checkpoint
is inaccessible or verification has already run, the harness refuses fault
injection. Failed recognized navigation is BLOCKED rather than proof of a
product defect. The harness does not invoke arbitrary dialogs or blind keystrokes.

## Limitations and safe alternatives

Standard Yes/No/OK IDs support localized Windows message boxes. Wizard navigation
currently recognizes English Inno Next/Install/Finish captions. Other captions,
UI Automation limitations or modal blocking can require a manual guest action
or another isolated VM with an observable Finish checkpoint.

For manual C1, stay inside a fresh Sandbox, install Core, accept downstream
conversion and stop at Finish. Confirm the successful-install log and absence
of conversion verification, then tamper only an installed manifest-owned
dependency, continue Finish, acknowledge the incomplete-conversion message and
collect the actual process exit. If the checkpoint is not available, use a
separate disposable VM with debugger/process suspension to hold the installed
payload before verification. Do not replace the verifier, rebuild revision 1
with different bytes, weaken integrity checks or infer exit 77 from a log alone.

These cases record the exact tested checkpoints; they do not establish arbitrary
mid-copy/power-loss interruption coverage or complete preservation of every
possible user setting. PRIVATE SUB production acceptance remains downstream.
The runner itself never merges a PR or changes its Draft status.
