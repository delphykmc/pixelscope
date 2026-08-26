# Active execution plan

Status: P7 Release Foundation active
Last updated: 2026-08-26
Baseline: `main@10294295f57a051b00ba205016c5318b6764ee66`

Repository Refactoring & Validation Hardening is complete through PR #55, the
manual-validation workflow regression fix is merged through PR #59, PR #60 activated
the dependency-independent P7 Release Foundation sequence, PR #61 completed the P7-A
PyInstaller `onedir` foundation, and PR #62 completed P7-B portable ZIP + Inno Setup
distribution with owner Windows artifact evidence and independent review.

P5-G remains **deferred** until the real external GPU server and SMB environment are
available:
[`../deferred/p5g-external-gpu-smb-validation.md`](../deferred/p5g-external-gpu-smb-validation.md).

P6 Identity, Access & Remote Operations also remains **planned / blocked for production
integration** until the external authentication and Remote IQA authority are known.
Do not infer P5-G PASS or activate production SSO from this plan.

While those external dependencies are unavailable, the repository may advance the
independent part of P7 as **P7 Release Foundation**. This is an explicit dependency
exception, not a P5-G bypass: packaging, installer, owner-local release-candidate
preparation, release metadata/manual-publication procedure, and notification-only
update foundations may proceed now. Production SSO and final packaged qualification
remain externally gated.

Authoritative active plan:
[`p7-release-foundation.md`](p7-release-foundation.md).

P7-0 packaging audit:
[`p7-packaging-audit.md`](p7-packaging-audit.md).

P7-B distribution audit:
[`p7-distribution-audit.md`](p7-distribution-audit.md).

P7-C owner-local release-candidate audit:
[`p7-release-candidate-audit.md`](p7-release-candidate-audit.md).

Current implementation slice: **P7-C — Owner-local Release Candidate Build & Validation**.
The implementation starts from the merged P7-B distribution contract and adds one
repository-owned Windows entry point that the authorized owner runs locally. It reuses
existing source checks and P7-A/P7-B build/smoke scripts, validates the strict final
production bundle, records exact source/tool/artifact provenance, and stages rendered
release notes beside the validated candidate artifacts.

P7-C does **not** require GitHub-hosted or self-hosted Actions and does not publish a
GitHub Release. Production publication, restricted-folder transfer, and signing
credentials remain beyond the repository automation boundary.

Current release sequence:

```text
P7-C Owner-local Release Candidate Build & Validation
    ↓
P7-D Metadata / Manual Publication / Notification-only Update Foundation
    ↓
P5-G External GPU/SMB Validation        # resume when environment is available
    ↓
P6 Identity, Access & Remote Operations # SSO implementation after contracts are authoritative
    ↓
P7-E Final Release Qualification        # packaged verification of P5-G/P6 + final release policy
```

P7-E does not implement SSO. P6 owns Identity & Access. P7-E only verifies the
already-implemented P6 authentication/remote behavior in the final packaged/installed
product together with P5-G real-environment behavior and final
install/upgrade/uninstall/signing checks.

The active P7 work must preserve existing application/runtime behavior and must not
invent SSO, API-authentication, SMB-authentication, signing-certificate, or privileged
corporate publication contracts that are not yet available.
