# P7-C Owner-local Release Candidate Audit

Status: Complete for repository-owned assumptions
Audited base: `main@10294295f57a051b00ba205016c5318b6764ee66`

P7-B is merged through PR #62. The repository has a validated Windows x64 PyInstaller
5.7 `onedir` build, deterministic portable ZIP, per-user Inno Setup installer, payload
manifest, third-party notices, and artifact smoke harnesses.

The original P7-C proposal assumed GitHub-hosted Windows runners and Actions artifact
retention. Review plus owner clarification established that this is not an executable
corporate release architecture. Corporate GitHub provides only self-hosted runners,
source/build context is owner-restricted, and production publication crosses a separate
security boundary with restricted authorized-folder access.

That earlier hosted-CI plan and its Inno 6.2.1 runner-isolation remediation are
superseded by this audit.

## Ownership boundary

P7-C owns a repository-defined release-candidate process that runs on the authorized
owner Windows development PC. It does not require either GitHub-hosted or self-hosted
Actions.

```text
Repository-owned / agent-safe
    test
    build
    smoke
    validate
    prepare candidate bundle
    prepare release notes / provenance
              ↓
validated owner-local release candidate
              ↓
CORPORATE SECURITY BOUNDARY
              ↓
authorized human publication / restricted-folder transfer
```

Manual authorized publication is a supported production path, not an automation
failure mode.

## Canonical candidate flow

The intended operational sequence is:

```text
Issue / implementation
    → PR
    → independent review
    → owner validation
    → merge to main
    → explicit owner release decision
    → owner-local release-candidate build
        repository validation
        canonical PyInstaller onedir build/validation/smoke
        portable ZIP build/smoke
        production installer build
        disposable-AppId installer install/run/uninstall smoke
        strict production-bundle validation
        provenance + rendered release-note staging
    → validated candidate/staging output
    → corporate authorization boundary
    → authorized user manually publishes approved artifacts
```

P7-C therefore establishes the candidate machinery before merge, but authoritative
candidate evidence is produced only when the owner explicitly runs it on the selected
merged source commit.

## Toolchain contract

P7-C does not introduce a CI-only compiler stack.

- Windows x64 remains required.
- CPython remains within the P7 release range `>=3.10.8,<3.11`.
- PyInstaller remains exactly `5.7` through `requirements/release.txt`.
- Inno Setup remains the P7-B supported range `>=6.1,<8`.
- `build_installer_release.py` retains existing `--iscc` / `ISCC_PATH` / PATH / common
  installation discovery.
- The candidate process resolves one `ISCC.exe`, passes that same compiler explicitly
  to the production installer build, exports it through `ISCC_PATH` for disposable
  smoke, and records its executable name, major version, and SHA-256 in candidate
  provenance. Local absolute tool paths are deliberately not persisted.
- No network download or installation of an artificial exact Inno version is required
  by the release contract.

The canonical `.iss` `Ver` guard remains authoritative for the exact supported
`>=6.1,<8` compile range.

## Repository-owned entry point

`scripts/build_release_candidate.py` is the P7-C owner-local orchestration entry point.
It defaults to:

```text
.venv/Scripts/python.exe          # repository/dev validation
.venv-release/Scripts/python.exe  # release/package tooling
```

and accepts explicit `--dev-python`, `--release-python`, and `--iscc` paths when the
corporate workstation layout differs.

Before building it requires a clean source worktree and captures the exact Git commit.
It removes only the ignored generated `release/` output before starting a fresh
candidate run.

The entry point reuses existing P7-A/P7-B scripts rather than duplicating packaging
logic. Any command failure aborts the candidate:

```text
scripts/check_docs.py
focused P7-C/P7-B release tests
full pytest -q
ruff check .
mypy src
pip check
git diff --check
release-env pip check
scripts/build_release.py
scripts/validate_release_artifact.py
scripts/smoke_packaged_release.py
scripts/build_portable_release.py
scripts/smoke_portable_release.py
scripts/build_installer_release.py
scripts/smoke_installer_release.py
scripts/validate_release_bundle.py
```

The known repository-wide `ruff format --check .` drift recorded during P7-B remains a
separate deferred cleanup item and is not silently relabeled as PASS by P7-C.

## Strict production bundle

`scripts/validate_release_bundle.py` is the generalized P7-C form of the useful bundle
validation originally prototyped for CI. It requires the generated `release/` root to
contain exactly the current-version production file set:

```text
PixelScope-<version>-windows-x64.manifest.json
PixelScope-<version>-windows-x64-THIRD_PARTY_NOTICES.txt
PixelScope-<version>-windows-x64-portable.zip
PixelScope-<version>-windows-x64-setup.exe
```

It rejects missing, extra, or empty files, rejects a disposable
`*-smoke-setup.exe`, and revalidates the payload manifest against the canonical
`dist/PixelScope/` tree.

## Candidate provenance and release-note staging

After the strict production bundle passes, the candidate entry point stages copies
under:

```text
release/candidate/PixelScope-<version>-windows-x64/
```

The staging directory contains the four validated production artifacts plus:

- `release-provenance.json` — canonical version, exact source commit, build timestamp,
  release Python executable name/version, PyInstaller version, actual Inno compiler
  executable name/major/SHA-256, release-note source, and staged artifact
  size/SHA-256 inventory. Local absolute machine paths are excluded;
- `RELEASE_NOTES.md` — rendered from the repository's dated/versioned release-note
  source with the exact source commit substituted.

The durable source for the current `0.1.0` candidate is
`docs/releases/2026-08-26-v0.1.0.md`.

P7-D owns the longer-term metadata/tag/manual-publication/update-provider contract. P7-C
only ensures a candidate can carry exact source provenance and a publication-ready note
source without publishing anything.

## Corporate publication boundary

P7-C must not:

- require GitHub Actions runners;
- upload Actions artifacts as authoritative release evidence;
- create a GitHub Release or tag;
- transfer artifacts into restricted publication folders;
- use signing certificates/private keys;
- claim unsigned candidates are production releases.

Production publication remains an explicit authorized user action beyond the
repository automation boundary.

## P7-C exit evidence

Repository implementation review should prove the owner-local pipeline and contracts
are correct. Before this PR can be merged, the owner should run applicable repository
and release-tooling validation on the branch.

A production release candidate itself is intentionally created only after merge and an
explicit owner release decision. For a selected merged source commit, P7-C candidate
PASS requires `scripts/build_release_candidate.py` to complete successfully and produce
the staged artifacts, rendered release notes, and provenance described above.

No GitHub-hosted or self-hosted workflow PASS is a P7-C exit criterion.

## Remaining release sequence

```text
P7-C owner-local release-candidate foundation
    → P7-D metadata / manual publication / notification-only update foundation
    → P5-G external GPU/SMB validation when environment is available
    → P6 Identity & Access / SSO implementation
    → P7-E final packaged-product qualification
```

P7-E does not implement SSO. P6 owns Identity & Access. P7-E only verifies the
already-implemented P6 behavior, P5-G real-environment behavior, and final
install/upgrade/uninstall/signing policy in the packaged product.
