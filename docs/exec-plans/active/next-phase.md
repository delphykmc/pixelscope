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
exception, not a P5-G bypass: packaging, installer, versioning, release automation, and
update-metadata foundations may proceed now, while SSO-dependent final qualification
remains deferred until P6 is complete.

Authoritative active plan:
[`p7-release-foundation.md`](p7-release-foundation.md).

P7-0 packaging audit:
[`p7-packaging-audit.md`](p7-packaging-audit.md).

P7-B distribution audit:
[`p7-distribution-audit.md`](p7-distribution-audit.md).

P7-C hosted CI audit:
[`p7-ci-audit.md`](p7-ci-audit.md).

Current implementation slice: **P7-C — Windows CI Artifact Pipeline**.
The implementation starts from the merged P7-B distribution contract and adds a
cache-independent GitHub-hosted Windows build that repeats source checks, PyInstaller
build/smoke, portable build/smoke, Inno installer build/smoke, and strict release-bundle
validation before retaining CI artifacts. The hosted toolchain is pinned and the
workflow has read-only repository permission. It does not publish a GitHub Release or
use production signing credentials.

P7-C closes only after a hosted `windows-2022` workflow run on the exact reviewed branch
state passes and the validated production distribution bundle is retained as a GitHub
Actions artifact.

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
