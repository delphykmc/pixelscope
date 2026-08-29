# Build and release runbook

This is the human-facing Windows Beta build/release procedure. Normative packaging,
artifact, installer, provenance, and publication rules remain in
[`PACKAGING_CONSTRAINTS.md`](PACKAGING_CONSTRAINTS.md); this runbook does not replace
that contract.

## Beta qualification boundary

The current Beta qualifies the local PixelScope desktop application and the existing
P7 executable/portable/installer/candidate/publication tooling. Production Remote IQA
server/GPU integration, full external result-writer/SMB qualification, and production
SSO/authentication are **not** Beta qualification gates. Repository tooling must not
invent or implement those external contracts as part of a Beta build.

## 1. Prepare the two Python environments

Use Windows x64 CPython `>=3.10.8,<3.11`.

The development environment owns repository validation:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\runtime.txt
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

The isolated release environment owns PyInstaller and distribution builds:

```powershell
py -3.10 -m venv .venv-release
.\.venv-release\Scripts\python.exe -m pip install -r requirements\release.txt
```

Do not install a different PyInstaller version into the release environment. The
normative contract requires exactly PyInstaller 5.7.

## 2. Check version, release notes, and external prerequisites

The only release-version authority is:

```text
src/pixelscope/version.py::__version__
```

Before building, ensure `docs/releases/` contains exactly one dated
`*-v<version>.md` source for that version and that it retains the
`{{SOURCE_COMMIT}}` marker consumed by the candidate builder.

Also require:

- Git available on `PATH`;
- a clean source worktree at the exact candidate commit;
- supported Inno Setup `>=6.1,<8` with `ISCC.exe` discoverable by the existing tooling,
  `ISCC_PATH`, or explicit `--iscc`;
- no dependency/spec/installer edits left uncommitted.

## 3. Build the owner-local release candidate

From repository root:

```powershell
.\.venv\Scripts\python.exe scripts\build_release_candidate.py
```

If compiler discovery is not appropriate on the owner PC:

```powershell
.\.venv\Scripts\python.exe scripts\build_release_candidate.py `
    --iscc "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

The entry point is the canonical Beta build path. It runs repository validation with
`.venv`, builds and smokes the packaged/portable/installer outputs with
`.venv-release`, validates the release bundle, and stages provenance/release notes.
A failure in any step is a failed candidate.

Successful candidate staging is:

```text
release/candidate/PixelScope-<version>-windows-x64/
```

The candidate contains the validated production distribution artifacts plus
`release-provenance.json` and rendered `RELEASE_NOTES.md`. The production distribution
files are version-derived and include the portable ZIP and Inno Setup installer, for
example:

```text
PixelScope-<version>-windows-x64-portable.zip
PixelScope-<version>-windows-x64-setup.exe
```

Use the files from the validated candidate directory for Beta handoff. Do not substitute
an older `dist/`, raw `release/`, or locally modified artifact after candidate PASS.

## 4. Beta distribution checks

### Installer

Run the candidate `*-setup.exe` interactively on Windows. The current contract is a
per-user install. Verify normal install/startup, the optional post-install
**Launch PixelScope** checkbox, and the expected upgrade/reinstall/downgrade prompt when
an existing installation is present.

### Portable ZIP

Extract the candidate `*-portable.zip` into a new directory and start the packaged
`PixelScope.exe` from that extracted payload. Do not mix files from another build into
the extracted directory.

For this Beta UI hardening release, also execute the PR's Windows UI/manual checklist on
the packaged build, especially Two Image + IQA resizing and floating Plots/IQA on the
available monitor configuration.

## 5. Prepare provider-neutral publication staging

Publication preparation consumes the exact candidate and requires the checkout commit
to equal candidate provenance:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_release_publication.py
.\.venv\Scripts\python.exe scripts\validate_release_publication.py
```

Successful staging is:

```text
release/publication/PixelScope-<version>-windows-x64/
```

If the authorized canonical local tag already exists immediately before publication,
validate it without creating or pushing anything:

```powershell
.\.venv\Scripts\python.exe scripts\validate_release_publication.py --require-tag
```

## 6. Corporate publication boundary

Repository scripts stop at build, validate, hash, render, candidate staging, and
provider-neutral publication staging. Production corporate release creation, approved
asset upload/transfer, tag publication, access/visibility checks, signing credentials,
and other privileged actions remain authorized human procedures across the corporate
security boundary.

After human publication, verify the remote release/tag resolves to the exact
`source_commit` in candidate provenance and verify uploaded artifact filenames and
SHA-256 identity. Local `--require-tag` is not a replacement for this remote check.

## 7. When previous evidence becomes stale

Rebuild the release candidate when any change can affect the application or generated
distribution, including runtime/source code, packaged resources, version/release notes,
requirements, PyInstaller spec/build scripts, installer definition/tooling, or portable
bundle tooling. UI source changes therefore require a new candidate even when numerical
semantics are unchanged.

After any candidate artifact, provenance, release-note, version, or source-commit change,
rerun publication preparation and validation before publication.

Test/docs-only changes may reuse prior artifact evidence only when review establishes
that they cannot change generated distribution contents. When that cannot be shown,
rebuild rather than carrying stale evidence forward.
