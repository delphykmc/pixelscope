# Optional downstream packaging capabilities (Issue #176)

PUBLIC MAIN owns packaging contracts; private distributions own their actual
descriptors, specs, dependencies, signing policy, provider code, and immutable
product identity. These opt-ins never alter default Core or Reference builds.

## Schema v1 additive fields (M1)

Only caller-selected custom target descriptors may set:

- `supersedes_installer_app_ids`: optional **nonempty array** of brace-wrapped
  GUID strings. The sole supported predecessor is the PUBLIC **per-user Core**
  AppId `{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}`. Duplicate GUIDs,
  self-supersession, malformed GUIDs, and all other predecessor identities are
  rejected. Omitting the field produces an empty tuple and **no conversion**.
  This field is only a declaration of intent; it is **not** permission to
  uninstall anything and must never trigger unattended removal by itself.
- `release_revision`: optional JSON integer between 0 and 65535 inclusive;
  booleans, floats, strings, and explicit JSON null are rejected. Omitting it preserves the
  canonical PUBLIC source release version and normal artifact naming. The
  release revision must be immutable for an already published downstream
  payload. Distribution revision and main source revision are distinct.

Downstream `target_id` cannot be `core` or `reference`, and downstream
`installer_app_id` must not equal Core AppId. Downstream output directory
may not alias `PixelScope` or `PixelScopeReference`; executable stem must
equal that output directory name.

Only per-user, HKCU uninstall registration is in scope for a future conversion
mechanism. Machine-wide, cross-user, arbitrary-path, and portable install
uninstalls are explicitly unsupported. Neither descriptor field grants
administrator privileges or broadens the uninstall allowlist.

This is an additive schema v1 change: existing descriptors work unchanged.
The explicit packaging scripts must be called with `--target-descriptor`;
PUBLIC builds never inspect a private directory automatically.

## Downstream effective distribution version (M2)

For an explicit custom descriptor with `release_revision=N`, the effective
version is `<PUBLIC_MAJOR>.<PUBLIC_MINOR>.<PUBLIC_PATCH>.<N>`; e.g. `0.1.0.2`.
It drives Windows file/product VERSIONINFO generated at
`build/release/<app_dir>.version.txt`, Inno `AppVersion` and packed comparison,
manifest `version`, names of four release artifacts, ZIP root and both smoke
validators. Custom PyInstaller specs **must consume that generated VERSIONINFO**
file and must not override the version independently. The frozen application
may still display the PUBLIC Core runtime version (`version.py`); the revision
identifies the *distribution*, not a separate Core codebase.

Revised builds require both 40-hex commit variables:

- `PIXELSCOPE_PUBLIC_MAIN_SHA`: exact public MAIN baseline commit.
- `PIXELSCOPE_DOWNSTREAM_SHA`: exact downstream source commit.

These are stored in manifest `build_provenance`, not in product version; the
release owner must verify that the hashes refer to the actual source tree. If
an existing revisioned manifest differs from the rebuilt payload hashes or
commits, the build fails rather than reusing the same release identity.
For PRIVATE SUB Windows acceptance, inspect the *built* executable rather
than assuming the generated VERSIONINFO was consumed by its spec:

```powershell
$exe = Get-Item .\\dist\\PixelScopeEnterprise\\PixelScopeEnterprise.exe
$exe.VersionInfo.FileVersion  # must be e.g. 0.1.0.2
$exe.VersionInfo.ProductVersion
Get-ChildItem .\\release\\PixelScopeEnterprise-0.1.0.2-windows-x64* -File |
  Get-FileHash -Algorithm SHA256  # archive externally as immutable release inventory
```

Check the installed executable and Inno setup four-part version as well, on a
*disposable* Windows test user. The workspace manifest guard alone does not
protect a previously published version in a new workspace; publishing must
check the release inventory against all four final SHA-256 artifact identities.

For PRIVATE SUB Windows acceptance, inspect the *built* executable rather
than assuming the generated VERSIONINFO was consumed by its spec:

```powershell
$exe = Get-Item .\\dist\\PixelScopeEnterprise\\PixelScopeEnterprise.exe
$exe.VersionInfo.FileVersion  # must be e.g. 0.1.0.2
$exe.VersionInfo.ProductVersion
Get-ChildItem .\\release\\PixelScopeEnterprise-0.1.0.2-windows-x64* -File |
  Get-FileHash -Algorithm SHA256  # archive externally as immutable release inventory
```

Check the installed executable and Inno setup four-part version as well, on a
*disposable* Windows test user. The workspace manifest guard alone does not
protect a previously published version in a new workspace; publishing must
check the release inventory against all four final SHA-256 artifact identities.

Revisions must be incremented for each changed downstream payload, even when
MAIN Core `version.py` has not changed. The release owner must preserve a
published release inventory, since a fresh workspace cannot detect prior
releases whose manifests have been deleted. Core/Reference manifest schemas,
names and product versions remain unchanged when opt-ins are absent.

## Optional Core -> downstream conversion (M3)

When the known PUBLIC Core predecessor is declared in a custom target
descriptor, the shared Inno script receives that **single allowlisted**
predecessor identity plus the SHA-256 values of the release manifest and
frozen executable. The normal PUBLIC and Reference installers do not receive
those defines, and **smoke installers intentionally disable conversion**
even when a custom descriptor declares a predecessor.

### Install lifecycle

1. Detect a registered PUBLIC Core installation in the current user's HKCU64
   uninstall key. Refuse unsupported HKLM/machine installations, missing
   registration fields, non-canonical Core install location, missing
   `PixelScope.exe`, invalid FileVersion, absent `unins000.exe/.dat`, or
   unexpected registered uninstall command. Reject install-file reparse points.
   Existing unregistered portable copies are never removed.
2. If Core is found, require explicit **Yes** with **No as the default**
   interactively. For `/SILENT` or `/VERYSILENT`, require
   **`/ALLOWCORECONVERSION=1`**; otherwise Setup aborts before installation.
   `/SUPPRESSMSGBOXES` is not consent and cannot override this requirement.
3. Check that the Core process is not running via Windows PowerShell
   (`Get-Process -Name PixelScope`) and refuse to proceed if the check fails
   or is unavailable. Recheck registry and running-process state in
   `PrepareToInstall`, and require the standard separate downstream folder.
   The installer does not kill the Core process or delete user settings.
4. Complete the downstream install with its **distinct AppId** first.
   At `ssDone`, require new HKCU64 registration, installed manifest and
   executable, matching compiled SHA-256 hashes, the expected four-part
   Windows FileVersion, and the correct downstream `InstallLocation`. The
   bundled, offline `packaging/installer/verify_downstream_payload.ps1`
   additionally walks **every manifest-owned file** (including DLLs, Qt
   plugins, Python runtime and resources), validating its relative path,
   reparse-point boundaries, size and SHA-256. A missing/corrupt dependency
   fails conversion while preserving Core. Only then re-validate Core and
   execute its exact registered uninstaller.
5. Verify Core uninstall exit code and disappearance of its registration,
   executable and uninstaller. On late failure, preserve the installed
   downstream edition, print a **PARTIAL CONVERSION** log and return custom
   **nonzero exit code 77**. No automatic rollback is promised.
6. With Core absent, future downstream->downstream releases follow the
   independent downstream AppId and ordinary version comparison; the
   predecessor removal path does not run.

For unattended deployment, enable `/LOG` so actionable evidence survives
failures. Interactive launch of the new edition is suppressed during a
conversion. After a partial conversion, inspect the logged failure, verify both
installations, repair the issue and rerun with explicit consent. Do not regard
an exit code other than zero as successful conversion.

### Windows-only isolated acceptance

**Do not run conversion tests against the developer's installed Core.**
Use a disposable Windows 10/11 x64 VM snapshot/test user with disposable
downstream AppId, fresh local user state and a separately installed disposable
PUBLIC Core instance. Keep VM snapshot checkpoints before every failure test.
PUBLIC Core still carries its normal GUID, so even test Core must be
restricted to this disposable environment.

Build with the authorized downstream descriptor and pinned exact commits,
for example in PowerShell:

```powershell
$env:PIXELSCOPE_PUBLIC_MAIN_SHA = "<40-hex-main-commit>"
$env:PIXELSCOPE_DOWNSTREAM_SHA = "<40-hex-downstream-commit>"
.\.venv-release\Scripts\python.exe scripts\build_release.py --target-descriptor path\target.json
.\.venv-release\Scripts\python.exe scripts\build_portable_release.py --target-descriptor path\target.json
.\.venv-release\Scripts\python.exe scripts\build_installer_release.py --target-descriptor path\target.json
.\.venv-release\Scripts\python.exe scripts\validate_release_bundle.py --target-descriptor path\target.json
```

Test matrix, each in a fresh VM state:

| Scenario | Required result |
| --- | --- |
| Fresh downstream install, no Core | Setup succeeds; distinct AppId present |
| Downstream same-AppId revision 1 -> 2 | Upgrade compares 4-part versions; no false reinstall |
| Core -> downstream, interactive No | Setup aborts; Core unchanged |
| Core -> downstream, interactive Yes | Downstream validates, then Core uninstalls |
| Core -> downstream, silent without switch | Nonzero; no new edition and Core unchanged |
| Core -> downstream, silent with switch | Success; Core removed |
| Stale/unreadable Core uninstall key or reparse point | Nonzero; no deletion |
| Running Core | Setup refuses; no force-termination |
| Downstream copy/manifest/EXE/DLL/plugin/resource fault | Core remains usable |
| Core uninstaller exits nonzero or leaves owned files | Nonzero (77 after completed install), partial state reported |
| Interruption between edition install and Core removal | Core retained; retry with consent is safe |
| PUBLIC Core/Reference installer | No conversion code, unchanged product/version/AppId |

For silent tests use an explicit `/LOG=<vm-test-log-path>` and capture
`$LASTEXITCODE`, HKCU64 and HKLM uninstall registrations, install folders,
manifest/executable hashes, process state, and QSettings before/after. The
normal `smoke_installer_release.py` is intentionally **not** a destructive
Core migration test. Inno compile and VM failure injection are mandatory
before declaring M3 production-ready. The code review and Python unit
tests alone cannot establish those runtime guarantees.
