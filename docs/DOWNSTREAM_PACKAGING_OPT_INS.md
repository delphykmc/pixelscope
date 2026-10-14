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

Revisions must be incremented for each changed downstream payload, even when
MAIN Core `version.py` has not changed. The release owner must preserve a
published release inventory, since a fresh workspace cannot detect prior
releases whose manifests have been deleted. Core/Reference manifest schemas,
names and product versions remain unchanged when opt-ins are absent.

## Conversion (M3)

M3 is tracked separately in #176. Merely setting the predecessor descriptor
field does not authorize or perform conversion.
