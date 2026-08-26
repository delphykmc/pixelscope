# Active execution plan

Status: P7-D Stage 1 active
Last updated: 2026-08-27
Baseline: `main@1fa6d278fcb16ed5170c3a21fc8cb31119f6e7e2`

Repository Refactoring & Validation Hardening is complete through PR #55. PR #60
activated the dependency-independent P7 Release Foundation sequence, PR #61 completed
P7-A PyInstaller `onedir`, PR #62 completed P7-B portable ZIP + Inno Setup, and PR #63
completed P7-C Owner-local Release Candidate Build & Validation at merge commit
`f3b1437b478e119c425dbf00d627b37f0371889e`.

P5-G remains **deferred** until the real external GPU server and SMB environment are
available:
[`../deferred/p5g-external-gpu-smb-validation.md`](../deferred/p5g-external-gpu-smb-validation.md).
No P5-G PASS is inferred from release work.

P6 Identity, Access & Remote Operations remains **planned / production-integration
gated** until the external authentication and Remote IQA authority are known. If
authoritative corporate identity/authentication documentation becomes available earlier,
a P6-0 contract audit/research slice may proceed before P5-G, but it must not implement
production SSO, alter Remote IQA authorization, issue/store tokens, or invent server
contracts.

The current independently executable work is **P7-D Stage 1 — Release Metadata & Manual
Publication Foundation**. It consumes the P7-C validated release candidate and adds
provider-neutral publication metadata, version/tag/note/artifact consistency checks,
and an explicit authorized manual publication procedure. It does not publish a release,
use production credentials, or change runtime/network behavior.

Authoritative P7 plan:
[`p7-release-foundation.md`](p7-release-foundation.md).

P7-C owner-local release-candidate audit:
[`p7-release-candidate-audit.md`](p7-release-candidate-audit.md).

P7-D Stage 1 publication audit:
[`p7-release-publication-audit.md`](p7-release-publication-audit.md).

Current release sequence:

```text
P7-A PyInstaller Foundation                         COMPLETE
    ↓
P7-B Portable ZIP / Inno Setup                     COMPLETE
    ↓
P7-C Owner-local Release Candidate                 COMPLETE — PR #63
    ↓
P7-D Stage 1 Release Metadata & Manual Publication ACTIVE
    ↓
P5-G External GPU/SMB Validation                   DEFERRED — real environment required
    ↓
P6 Identity, Access & Remote Operations            PLANNED / production integration gated
    ↓
P7-D Stage 2 Notification-only Update Discovery    DEFERRED — provider/auth authority pending
    ↓
P7-E Final Release Qualification                   DEFERRED
```

P7-D Stage 2 is deliberately outside the current implementation slice. The durable
update rule is:

> **Update discovery must never initiate authentication.**

Stage 1 does not establish whether the eventual authoritative update provider requires
application authentication. If it does, a future implementation may use only an
already-established approved P6 capability and otherwise skips discovery silently. If
an authoritative provider is explicitly usable without application authentication,
that path remains permitted. Provider selection and any authentication mechanism remain
deferred until the relevant P6/provider contracts are authoritative.

P7-E does not implement SSO. P6 owns Identity & Access. P7-E only verifies any
already-implemented P6 authentication/remote behavior in the final packaged product,
together with P5-G real-environment behavior and final install/upgrade/uninstall,
signing, and release-policy checks.

The active work must preserve existing application/runtime behavior and must not invent
SSO, API-authentication, SMB-authentication, signing-certificate, privileged corporate
publication, or update-provider contracts that are not yet authoritative.
