# Active execution plan

Status: P7 Release Foundation active
Last updated: 2026-08-26
Baseline: `main@62258d24305b8d4974419aba8f9d2b2ed9c7a965`

Repository Refactoring & Validation Hardening is complete through PR #55, and the
manual-validation workflow regression fix is merged through PR #59.

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
