# P7 Release Foundation — Active execution plan

Status: Active — P7-D Stage 1
Activated: 2026-08-26
Current baseline: `main@1fa6d278fcb16ed5170c3a21fc8cb31119f6e7e2`

## 1. Purpose

P7 Release Foundation establishes a repeatable Windows distribution, release-candidate,
and manual-publication preparation process while P5-G waits for the real external
GPU/SMB environment and P6 waits for authoritative corporate identity/authentication
contracts.

This is an explicit dependency exception. It does **not** mark P5-G complete, activate
production SSO, or declare PixelScope release-ready. It advances only work that is
independent of those external contracts.

The corporate release boundary confirmed during P7-C means repository automation owns
candidate preparation and P7-D Stage 1 publication preparation, but production
publication remains an authorized human action. Neither GitHub-hosted nor self-hosted
Actions are required for this foundation.

Current intended sequence:

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

## 2. Repository baseline

At P7 activation time:

- runtime supported Python `>=3.10,<3.11`;
- package version was `0.1.0`;
- console entry point was `pixelscope = pixelscope.app.application:main`;
- application icon assets were already package data;
- there was no GitHub Actions release workflow;
- PyInstaller was not part of the development requirements;
- ROADMAP required exactly PyInstaller 5.7 `onedir`, portable ZIP, Inno Setup,
  clean-PC smoke testing, signing, update strategy review, and a repeatable release
  process.

Those are activation-time facts only. P7-A/P7-B/P7-C have since established the
executable, distribution, and owner-local candidate foundations. P7-C merged as PR #63
at `f3b1437b478e119c425dbf00d627b37f0371889e`. Every later slice must re-check the
exact merged state rather than treating the activation snapshot as current
implementation status.

## 3. Release-foundation contract

### 3.1 Canonical build shape

The first supported Windows executable build is:

- Windows x64;
- Python 3.10;
- exactly PyInstaller 5.7;
- `onedir`, not `onefile`;
- GUI application behavior preserved without introducing a second application entry
  point;
- existing PixelScope icon assets used for the executable/installer where technically
  applicable;
- generated files kept out of source-controlled runtime/package directories.

A build must start from a clean/reproducible repository state and must not encode a
particular developer machine's absolute paths into shipped artifacts.

### 3.2 Version authority

P7 has one canonical application/release version authority:
`src/pixelscope/version.py::__version__`.

Build metadata, portable ZIP, installer metadata, artifact names, release-note identity,
release tag/title, candidate provenance, and P7-D Stage 1 publication metadata must
derive from that authority rather than carrying independently edited version strings.

Do not invent semantic-version bump policy beyond what is needed to make the authority
single-source and executable.

### 3.3 Artifact lineage

The portable ZIP and Inno Setup installer consume the **same validated PyInstaller
`onedir` output**. They must not perform separate hidden application builds with
potentially different dependency contents.

Conceptually:

```text
source + pinned release tooling
          ↓
PyInstaller 5.7 onedir
          ↓ validate
canonical dist/PixelScope/
      ├── portable ZIP
      └── Inno Setup installer
```

P7-C owns the strict production distribution set and candidate staging. The shared
`scripts/release_candidate_contract.py` owns the exact current candidate provenance
schema consumed by both P7-C writing and P7-D validation. P7-D Stage 1 must consume that
candidate and must not redefine either the four-file distribution bundle or candidate
provenance schema.

### 3.4 Installed and portable behavior

P7 foundation preserves existing application contracts:

- application settings remain user/machine state, not baked into release artifacts;
- installation must not silently delete user settings on upgrade/uninstall unless an
  explicit future policy says otherwise;
- current local Files/Session/Recent/Remote IQA data contracts are unchanged;
- no release step may modify source data or Remote IQA result data;
- no administrator privilege should be required by the application merely to run after
  installation.

The installer scope and installation directory policy remain explicit and testable.

### 3.5 Release-candidate and publication boundary

The repository owns deterministic validation/build/smoke logic, preparation of a
release candidate on the authorized Windows development PC, and provider-neutral
publication preparation/validation.

The canonical ownership split is:

```text
Repository-owned / agent-safe
    test
    build
    smoke
    validate
    prepare candidate bundle
    prepare release notes / provenance
    prepare publication metadata / checklist
              ↓
validated owner-local publication staging
              ↓
CORPORATE SECURITY BOUNDARY
              ↓
authorized human publication / restricted-folder transfer / privileged signing
```

Production GitHub Enterprise Release upload is not a repository automation requirement.
Manual authorized upload is the supported production publication path unless a later
corporate-approved mechanism explicitly changes that contract.

An ordinary branch push, merge, local candidate build, or P7-D preparation command must
never silently create/publish a production release.

The manual production procedure must verify both sides of release identity: local
pre-publication tag validation and, after publication, an authorized-human check that
the remote corporate release/tag resolves to the same exact candidate provenance
`source_commit`, together with uploaded asset filename/hash and visibility/access checks.

### 3.6 Notification-only update discovery boundary — deferred P7-D Stage 2

P7-D Stage 1 does **not** implement runtime update discovery. The eventual provider and
its access requirements are not authoritative yet, so runtime integration is deferred
to P7-D Stage 2 after the relevant P6/provider contracts are known.

The durable rule is:

> **Update discovery must never initiate authentication.**

Stage 1 does not establish whether the selected update-metadata provider requires
application authentication. If the provider requires authentication, a future update
check may use only an already-established approved P6 capability and must silently skip
discovery when that capability is unavailable. If an authoritative provider is
explicitly usable without application authentication, this contract does not prohibit
that path.

P7-D Stage 1 establishes no common-IdP topology and does not select OAuth App, GitHub App,
PAT, bearer-token reuse, token exchange, or browser-cookie reuse. After the relevant
P6/provider contracts are authoritative, Stage 2 may compare provider options such as:

- an IQA/PixelScope backend release-metadata endpoint;
- an approved corporate platform metadata endpoint;
- the corporate GitHub Enterprise Releases API with an approved GitHub authentication
  mechanism when that provider actually requires it.

An explicit future **View Release** action may open an approved release page in the
system browser. Browser authentication and repository/release authorization, if
required, remain browser/platform responsibilities. PixelScope must not read, copy, or
persist browser SSO cookies.

PixelScope/IQA application entitlement and GitHub source/release repository membership
must not be assumed to be the same authorization domain.

### 3.7 Signing boundary

Production signing is deferred until certificate ownership, secret storage, and
corporate release policy are authoritative.

P7 foundation may provide a documented signing hook/interface, but it must not:

- commit certificates/private keys;
- invent production credentials;
- require a fake signing step for local development;
- claim unsigned artifacts are production-signed.

## 4. Explicit non-goals

P7-D Stage 1 does not implement or redefine:

- startup or periodic update checks;
- update notification UI;
- GitHub Enterprise API clients;
- corporate Login / SSO;
- OAuth/OIDC/SAML selection;
- OAuth App / GitHub App / PAT selection;
- access/refresh-token lifecycle;
- token storage or refresh;
- browser cookie access;
- Remote IQA bearer-token or authorization contracts;
- SMB authentication/impersonation;
- server permission or audit policy;
- P5-G real-environment validation;
- production code-signing credentials;
- automatic/self update, download, installer launch, rollback, or privilege escalation;
- Microsoft Store/MSIX migration;
- a switch from PyInstaller 5.7 `onedir` to another bundler;
- a mandatory GitHub-hosted or self-hosted release runner;
- automated privileged production publication.

If packaging/publication validation exposes a repository defect, fix only the smallest
repository-owned issue necessary and preserve existing runtime contracts. Do not use P7
as a general refactoring phase.

## 5. Execution slices

Each implementation slice should be independently reviewable. P7-D remains one phase
with two stages rather than becoming additional numbered phases.

| Order | Slice | Goal | Exit evidence |
|---|---|---|---|
| P7-0 | Release contract & packaging audit | Reconcile current entry point, resources, versioning, dependency/runtime assumptions and freeze the executable release contract | Complete; docs/checks PASS; no runtime behavior change |
| P7-A | PyInstaller onedir foundation | Add pinned PyInstaller 5.7 release tooling, deterministic spec/build entry point, required data/hidden-import handling, and executable smoke validation | Complete — PR #61; owner clean Windows build and packaged-resource smoke |
| P7-B | Portable ZIP & Inno Setup | Produce both distribution forms from the same validated onedir tree; define install/uninstall/upgrade and artifact naming rules | Complete — PR #62; ZIP + installer compile/install/run/uninstall smoke |
| P7-C | Owner-local Release Candidate Build & Validation | Reuse P7-A/P7-B checks/build/smoke, validate the strict production bundle, and stage exact provenance/release notes | Complete — PR #63; owner-local pipeline implemented/reviewed |
| P7-D Stage 1 | Release Metadata & Manual Publication Foundation | Enforce version/tag/title/note/artifact/provenance consistency and prepare provider-neutral publication metadata plus the authorized manual publication procedure | Active; focused publication tests + documented manual publication contract; no runtime/network auth behavior |
| P7-D Stage 2 | Notification-only Update Discovery/Integration | After provider/P6 authority, optionally integrate notification-only update discovery without initiating authentication | Deferred; provider/access contract must be authoritative before implementation |
| P7-E | Final Release Qualification | After P5-G, P6, and any selected P7-D Stage 2 work, validate the integrated remote/auth behavior in the packaged product plus clean-PC install/upgrade/uninstall, signing, and final release policy | Deferred until dependencies complete |

P7-E does **not** implement SSO. P6 owns Identity & Access / SSO implementation. P7-E
only qualifies the integrated packaged result.

### P6-0 research exception

P6 production integration remains sequenced after P5-G. If authoritative corporate
identity/authentication documentation becomes available earlier, a P6-0 contract
audit/research may proceed before production integration. P6-0 research must not
implement production SSO, modify Remote IQA authorization, issue/store credentials, or
invent server/API contracts. Its purpose is to establish the real corporate identity
architecture for later P6 and P7-D Stage 2 decisions.

## 6. P7-0 audit questions — historical foundation

Before P7-A, the program audited:

1. the executable composition root;
2. package-resource access under PyInstaller `onedir`;
3. required Qt/PySide6 plugins;
4. dependency collection/exclusions;
5. GUI console behavior;
6. generated build/dist/installer locations;
7. canonical version authority and derived release identities;
8. artifact smoke scope;
9. clean-PC prerequisites;
10. redistributed third-party notice obligations.

Those answers are now embodied in P7-A/B/C tooling and `docs/PACKAGING_CONSTRAINTS.md`.
P7-D Stage 1 reuses them rather than reopening the packaging architecture.

## 7. Validation policy

### Docs-only changes

When a slice changes only Markdown/documentation, run the repository documentation
checks only. Do not spend time running the full runtime suite solely for docs-only
changes.

### Source/build/test/tooling changes

When Python source, tests, dependency files, packaging scripts/specs, installer files,
release-candidate tooling, or publication tooling change, run the normal repository
validation applicable to that change, including at minimum:

- documentation contract checks when durable docs changed;
- focused tests for changed behavior/tooling;
- full pytest suite before slice closeout where the environment supports it;
- Ruff check;
- mypy;
- pip check;
- `git diff --check`;
- release-specific structural checks that do not falsely claim external publication.

P7-D Stage 1 adds no runtime/network behavior, so lack of Enterprise GitHub access is
not a reason to fake a PASS. Implementation tests prove metadata/preparation contracts;
actual corporate publication remains separate owner evidence after merge.

### External/manual evidence

Do not fabricate clean-PC, Inno Setup, signing, corporate publication, or external
environment PASS evidence. If an agent environment cannot execute a required
Windows/manual gate, automate everything it can, record the exact remaining owner
validation, and leave that gate pending.

No hosted/self-hosted Actions run is required to substitute for the authorized owner
Windows candidate build.

## 8. Review and merge policy

For every implementation slice:

1. start from the latest intended base and record the exact SHA;
2. use a dedicated branch;
3. keep commits small and purpose-specific;
4. open a PR with objective, contract, changed files, automated evidence, and remaining
   manual validation;
5. obtain an independent review against this plan and existing durable contracts;
6. fix review findings on the same branch and re-review latest HEAD;
7. merge only after blockers are resolved and required owner validation is recorded.

Do not carry PASS evidence from an earlier slice to a later changed HEAD.

P7-C implementation/review evidence proves the release-candidate machinery. A real
production candidate and publication are created only after merge from the exact source
commit selected by an explicit owner release decision.

P7-D Stage 1 implementation PR proves publication metadata/preparation/validation
machinery. It does **not** prove a corporate GitHub Enterprise Release was published.
After Stage 1 merge, the owner creates a fresh P7-C candidate from the selected merged
main commit before any actual publication procedure is executed.

## 9. Completion boundary

The dependency-independent release foundation is complete when P7-A through P7-D Stage
1 have established a repeatable, version-consistent Windows `onedir`
build/distribution/candidate/publication-preparation process with artifact-level
validation, exact provenance, and an explicit manual-publication boundary.

P7-D Stage 2 is not part of that dependency-independent completion gate. It remains an
optional notification-only update-discovery/integration decision after the relevant
P6/provider authority is known; authentication is not assumed to be an inherent
provider requirement.

Foundation completion does **not** mean PixelScope is production-release complete.
Final P7 closeout remains blocked on P7-E, which follows real P5-G validation and P6
identity/access integration. P7-E owns final packaged verification of those already
implemented behaviors, clean-PC qualification, production signing/policy validation,
and release closeout.
