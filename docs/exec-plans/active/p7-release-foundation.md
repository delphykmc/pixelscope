# P7 Release Foundation — Active execution plan

Status: Active
Activated: 2026-08-26
Baseline: `main@62258d24305b8d4974419aba8f9d2b2ed9c7a965`

## 1. Purpose

P7 Release Foundation establishes a repeatable Windows distribution and release-candidate
process while P5-G waits for the real external GPU/SMB environment and P6 waits for
authoritative corporate SSO/authentication contracts.

This is an explicit dependency exception. It does **not** mark P5-G complete, activate
production SSO, or declare PixelScope release-ready. It advances only work that is
independent of those external contracts.

The corporate release boundary confirmed during P7-C means repository automation owns
candidate preparation, but production publication remains an authorized human action.
Neither GitHub-hosted nor self-hosted Actions are required for P7 completion.

Current intended sequence:

```text
P7-C Owner-local Release Candidate Build & Validation
    ↓
P7-D Metadata / Manual Publication / Notification-only Update Foundation
    ↓
P5-G External GPU/SMB Validation        # when environment becomes available
    ↓
P6 Identity, Access & Remote Operations # SSO implementation when auth contracts are authoritative
    ↓
P7-E Final Release Qualification        # packaged verification of P5-G/P6 + release closeout
```

## 2. Repository baseline

At activation time:

- runtime supports Python `>=3.10,<3.11`;
- package version is currently `0.1.0` in `pyproject.toml`;
- console entry point is `pixelscope = pixelscope.app.application:main`;
- application icon assets are already package data;
- there is no existing GitHub Actions workflow directory;
- PyInstaller is not yet part of the development requirements;
- ROADMAP requires exactly PyInstaller 5.7 `onedir`, portable ZIP, Inno Setup,
  clean-PC smoke testing, signing, update strategy, and a repeatable release process.

Those are activation-time facts only. P7-A/P7-B have since established the executable
and distribution foundations. Every implementation slice must re-check the exact merged
state rather than treating this activation snapshot as current implementation status.

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

P7 must establish one documented canonical application/release version authority.
Build, portable ZIP, installer metadata, release artifact names, release-note metadata,
and update metadata must derive from that authority rather than carrying independently
edited version strings.

Do not invent semantic-version bump policy beyond what is needed to make the authority
single-source and executable.

### 3.3 Artifact lineage

The portable ZIP and Inno Setup installer must consume the **same validated PyInstaller
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

### 3.4 Installed and portable behavior

P7 foundation must preserve existing application contracts:

- application settings remain user/machine state, not baked into release artifacts;
- installation must not silently delete user settings on upgrade/uninstall unless an
  explicit future policy says otherwise;
- current local Files/Session/Recent/Remote IQA data contracts are unchanged;
- no release step may modify source data or Remote IQA result data;
- no administrator privilege should be required by the application merely to run after
  installation.

The installer scope and installation directory policy must be explicit and testable.

### 3.5 Release-candidate and publication boundary

The repository owns deterministic validation/build/smoke logic and preparation of a
release candidate on the authorized Windows development PC. P7-C must remain complete
without a configured GitHub Actions runner.

The canonical ownership split is:

```text
Repository-owned / agent-safe
    test
    build
    smoke
    validate
    prepare candidate bundle
    prepare release notes / provenance
              ↓
CORPORATE SECURITY BOUNDARY
              ↓
authorized human publication / restricted-folder transfer / privileged signing
```

Production GitHub Release upload is not a repository automation requirement. Manual
authorized upload is the supported production publication path unless a later
corporate-approved mechanism explicitly changes that contract.

An ordinary branch push, merge, or local candidate build must never silently publish a
production release.

### 3.6 Update strategy boundary

Foundation work may define machine-readable release/version metadata and an abstraction
for checking whether a newer version exists. The first user-facing update behavior, if
implemented in this program, is **notification only**.

Do not implement self-update, silent download/install, rollback, privilege escalation,
or an installer-launching updater in Release Foundation.

The metadata/provider boundary must allow a later corporate release endpoint to replace
or coexist with GitHub Releases without changing core application/version semantics.

### 3.7 Signing boundary

Production signing is deferred until certificate ownership, secret storage, and
corporate release policy are authoritative.

P7 foundation may provide a documented signing hook/interface, but it must not:

- commit certificates/private keys;
- invent production credentials;
- require a fake signing step for local development;
- claim unsigned artifacts are production-signed.

## 4. Explicit non-goals

Release Foundation does not implement or redefine:

- corporate Login / SSO;
- OAuth/OIDC/SAML selection;
- access/refresh-token lifecycle;
- Remote IQA bearer-token or authorization contracts;
- SMB authentication/impersonation;
- server permission or audit policy;
- P5-G real-environment validation;
- production code-signing credentials;
- automatic/self update;
- Microsoft Store/MSIX migration;
- a switch from PyInstaller 5.7 `onedir` to another bundler;
- a mandatory GitHub-hosted or self-hosted release runner;
- automated privileged production publication.

If packaging exposes an application defect, fix only the smallest repository-owned
issue necessary and preserve existing runtime contracts. Do not use P7 as a general
refactoring phase.

## 5. Execution slices

Each slice should be independently reviewable. Prefer one PR per slice unless the
implementation audit proves two adjacent slices are inseparable.

| Order | Slice | Goal | Exit evidence |
|---|---|---|---|
| P7-0 | Release contract & packaging audit | Reconcile current entry point, resources, versioning, dependency/runtime assumptions and freeze the executable release contract | Complete; docs/checks PASS; no runtime behavior change |
| P7-A | PyInstaller onedir foundation | Add pinned PyInstaller 5.7 release tooling, deterministic spec/build entry point, required data/hidden-import handling, and executable smoke validation | Complete; owner clean Windows build and packaged-resource smoke |
| P7-B | Portable ZIP & Inno Setup | Produce both distribution forms from the same validated onedir tree; define install/uninstall/upgrade and artifact naming rules | Complete; ZIP + installer compile/install/run/uninstall smoke |
| P7-C | Owner-local Release Candidate Build & Validation | Provide one repository-owned Windows entry point that reuses P7-A/P7-B checks/build/smoke, validates the strict production bundle, and stages exact provenance/release notes | owner-local pipeline implemented/reviewed; selected merged candidate run produces validated staging output |
| P7-D | Release metadata, manual publication & update foundation | Enforce version/artifact/release-note metadata consistency, document the authorized manual publication procedure, and add notification-only update metadata/provider boundary if justified | dry-run/local metadata checks + documented manual publication contract; no automatic updater or privileged upload requirement |
| P7-E | Final Release Qualification | After P5-G and P6, validate the already-implemented remote/auth behavior in the packaged product plus clean-PC install/upgrade/uninstall, signing, and final release policy | deferred until dependencies complete |

P7-E does **not** implement SSO. P6 owns Identity & Access / SSO implementation. P7-E
only qualifies the integrated packaged result.

## 6. P7-0 audit questions

Before implementing P7-A, answer from the repository rather than assumption:

1. What is the actual executable entry point used by `python -m pixelscope` and the
   installed console script, and should the packaged GUI invoke the same composition
   root?
2. Which resources are accessed by package-resource APIs versus filesystem-relative
   paths, and will both work under PyInstaller `onedir`?
3. Which Qt/PySide6 plugins are required in a clean Windows deployment?
4. Which OpenCV, NumPy, pyqtgraph, httpx/Pydantic dependencies require explicit
   collection or exclusions under PyInstaller 5.7?
5. Does the application currently create consoles or rely on stdout/stderr in normal
   GUI use?
6. Where should generated build/dist/installer output live, and is `.gitignore`
   sufficient?
7. What is the canonical version source and how will Python runtime, executable file
   metadata, ZIP name, installer version/name, and release tag derive from it?
8. Which current tests can run against the packaged executable without becoming brittle
   UI automation?
9. What clean-PC prerequisites, if any, remain after bundling?
10. Are there licensing/notices obligations for redistributed third-party binaries that
    need an artifact-level notice?

Record audit results in durable docs before treating P7-A implementation choices as
contract.

## 7. Validation policy

### Docs-only changes

When a slice changes only Markdown/documentation, run the repository documentation
checks only. Do not spend time running the full runtime suite solely for docs-only
changes.

### Source/build/test/tooling changes

When Python source, tests, dependency files, packaging scripts/specs, installer files,
or release-candidate tooling change, run the normal repository validation applicable
to that change, including at minimum:

- documentation contract checks when durable docs changed;
- focused tests for changed behavior/tooling;
- full pytest suite before slice closeout where the environment supports it;
- ruff;
- mypy;
- release-specific structural/smoke checks.

The packaged executable/installer cannot be considered validated only because source
pytest passes. P7 requires artifact-level validation.

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

For P7-C specifically, the branch/PR proves the release-candidate machinery. The
candidate itself is built only after merge from the exact source commit selected by an
explicit owner release decision.

## 9. Completion boundary

Release Foundation is complete when P7-A through P7-D have established a repeatable,
version-consistent Windows `onedir` build/distribution/candidate process with
artifact-level validation, exact provenance, an explicit manual-publication boundary,
and a notification-only update-metadata boundary.

That completion does **not** mean PixelScope is production-release complete.

Final P7 closeout remains blocked on P7-E, which follows real P5-G validation and P6
identity/access integration. P7-E owns final packaged verification of those already
implemented behaviors, clean-PC qualification, production signing/policy validation,
and release closeout.
