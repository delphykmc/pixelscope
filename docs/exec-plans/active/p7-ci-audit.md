# P7-C Windows CI Audit

Status: Complete for repository-owned assumptions
Audited base: `main@10294295f57a051b00ba205016c5318b6764ee66`

P7-B is merged through PR #62. The repository now has a validated Windows x64
PyInstaller 5.7 `onedir` build, deterministic portable ZIP, per-user Inno Setup
installer, payload manifest, third-party notices, and local artifact smoke harnesses.
There is still no GitHub Actions workflow directory on the audited base.

P7-C adds hosted Windows build/validation and retained CI artifacts. It does not publish
a GitHub Release, create tags, sign binaries, or change application/runtime behavior.
Those publication/version-metadata responsibilities remain P7-D; production signing and
final clean-PC qualification remain P7-E.

## Hosted toolchain contract

P7-C pins the hosted build environment instead of using moving aliases where a stable
choice is available:

- runner: `windows-2022` x64;
- CPython: `3.10.11` x64;
- PyInstaller: exactly `5.7` through `requirements/release.txt`;
- Inno Setup: exactly `6.2.1`;
- Inno Setup installer source:
  `https://files.jrsoftware.org/is/6/innosetup-6.2.1.exe`;
- Inno Setup installer SHA-256:
  `50D21AAB83579245F88E2632A61B943AD47557E42B0F02E6CE2AFEF4CDD8DEB1`.

The Inno installer is downloaded from the vendor distribution location and its SHA-256
is verified before silent installation. CI must not silently accept a different Inno
binary under the same configured version.

Third-party GitHub Actions are pinned to immutable commit SHAs rather than moving major
or branch tags:

- `actions/checkout` v4.2.2 commit
  `11bd71901bbe5b1630ceea73d27597364c9af683`;
- `actions/setup-python` v5.6.0 commit
  `a26af69be951a213d495a4c3e4e4022e16d87065`;
- `actions/upload-artifact` v4.6.2 commit
  `ea165f8d65b6e75b540449e92b4886f43607fa02`.

P7-C does not introduce dependency caches. A successful hosted build must therefore be
correct from a fresh runner with fresh dependency installation. Cache optimization may
be added later only if it cannot become correctness authority.

## Trigger boundary

The workflow runs on:

- pull requests that touch artifact-affecting source, tests, requirements, packaging,
  release tooling, or the workflow itself;
- pushes to `main` for the same artifact-affecting paths;
- explicit `workflow_dispatch`.

Documentation-only changes outside the release/packaging contract do not need an
expensive Windows release build.

The workflow uses the `pull_request` event, not `pull_request_target`, and requires only
`contents: read`. P7-C introduces no repository or environment secrets and no write
permission.

## Validation topology

The job uses two isolated virtual environments derived from the same pinned hosted
CPython:

```text
.venv-ci      -> requirements/dev.txt
.venv-release -> requirements/release.txt
```

The development environment owns source/document validation:

```text
scripts/check_docs.py
pytest -q
ruff check .
mypy src
pip check
git diff --check
```

The known repository-wide `ruff format --check .` drift recorded during P7-B remains a
separate deferred cleanup item and is not silently relabeled as PASS by P7-C.

The release environment owns artifact generation and artifact-level validation:

```text
scripts/build_release.py
scripts/validate_release_artifact.py
scripts/smoke_packaged_release.py
scripts/build_portable_release.py
scripts/smoke_portable_release.py
scripts/build_installer_release.py
scripts/smoke_installer_release.py
scripts/validate_ci_release_bundle.py
```

The installer smoke continues to use the P7-B disposable smoke AppId, so a hosted run
exercises real install/run/uninstall mechanics without changing the production AppId
contract.

## Retained artifact contract

After all validation passes, CI retains exactly the production P7-B distribution set:

```text
release/PixelScope-<version>-windows-x64.manifest.json
release/PixelScope-<version>-windows-x64-THIRD_PARTY_NOTICES.txt
release/PixelScope-<version>-windows-x64-portable.zip
release/PixelScope-<version>-windows-x64-setup.exe
```

The disposable `*-smoke-setup.exe` is not a release artifact and must not be present at
upload time. Artifact retention is 14 days. Upload uses `if-no-files-found: error` and
occurs only after the bundle validator passes.

The Actions artifact is CI evidence, not a production release. P7-C does not create a
GitHub Release or publish binaries to a production channel.

## Exit evidence

P7-C closes only after a hosted `windows-2022` workflow run on the P7-C branch/PR proves:

1. source/document checks pass in a clean development environment;
2. the canonical PyInstaller 5.7 onedir builds and passes packaged smoke;
3. portable ZIP build/smoke passes;
4. exact Inno Setup 6.2.1 is installed from the hash-verified vendor binary;
5. production installer build passes;
6. disposable installer install/run/uninstall smoke passes;
7. the retained distribution bundle has exactly the expected production files;
8. GitHub Actions uploads the validated bundle successfully.

Local tests or code review cannot substitute for this hosted artifact evidence.

## Non-goals

P7-C does not add:

- GitHub Release creation or release asset publication;
- tag-triggered production publication;
- application version bump policy;
- update notification/provider behavior;
- signing certificates, keys, or SignTool credentials;
- self-update;
- P5-G external GPU/SMB validation;
- P6 SSO/authentication behavior;
- final clean-PC production qualification.
