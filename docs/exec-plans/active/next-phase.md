# Active execution plan

Status: P7 Release Foundation active
Last updated: 2026-08-26
Baseline: `main@8648b88ed7fd3a0af75013dd31633c48ccbce3e5`

Repository Refactoring & Validation Hardening is complete through PR #55, the
manual-validation workflow regression fix is merged through PR #59, and PR #60
activated the dependency-independent P7 Release Foundation sequence.

P5-G remains **deferred** until the real external GPU server and SMB environment are
available:
[`../deferred/p5g-external-gpu-smb-validation.md`](../deferred/p5g-external-gpu-smb-validation.md).

P6 Identity, Access & Remote Operations also remains **planned / blocked for production
integration** until the external authentication and Remote IQA authority are known.
Do not infer P5-G PASS or activate production SSO from this plan.

While those external dependencies are unavailable, the repository may advance the
independent part of P7 as **P7 Release Foundation**. This is an explicit dependency
exception, not a P5-G bypass: packaging, installer, versioning, release automation, and
update-metadata foundations may proceed now, while SSO-dependent final qualification
remains deferred until P6 is complete.

Authoritative active plan:
[`p7-release-foundation.md`](p7-release-foundation.md).

P7-0 packaging audit:
[`p7-packaging-audit.md`](p7-packaging-audit.md).

Current implementation slice: **P7-A — PyInstaller onedir foundation**.
The implementation branch establishes the canonical version authority, pinned release
tooling, PyInstaller 5.7 windowed `onedir` spec, deterministic build/output paths,
structural artifact validator, and external packaged-executable smoke harness.
Repository/source-level review can proceed independently, but P7-A cannot be closed
until the Windows artifact build/validation evidence is actually observed.

Current execution order:

```text
P7 Release Foundation
    ↓
P5-G External GPU/SMB Validation        # resume when environment is available
    ↓
P6 Identity, Access & Remote Operations # after server/auth contracts are authoritative
    ↓
P7 Final Release Qualification          # SSO-aware clean-PC/release closeout
```

The active P7 work must preserve existing application/runtime behavior and must not
invent SSO, API-authentication, SMB-authentication, signing-certificate, or corporate
distribution contracts that are not yet available.
