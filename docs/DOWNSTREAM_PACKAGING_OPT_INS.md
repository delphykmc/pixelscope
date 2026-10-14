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

M2 distribution version propagation and M3 consented conversion are tracked
separately in #176. They must not be claimed operational merely because a
descriptor passes M1 validation.
