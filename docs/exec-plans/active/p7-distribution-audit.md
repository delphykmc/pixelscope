# P7-B Distribution Audit

Status: Complete for repository-owned assumptions
Audited base: `main@9b9cd28a10e599659e8485fadddf8b6ac948fc7f`

This audit defines the repository-owned contract for P7-B. It does not claim that an
Inno Setup installer has been compiled, installed, or uninstalled on Windows yet.
It does not close P5-G, P6, P7-C/P7-D, or final P7-E qualification.

## Starting state

P7-A is merged through PR #61. The canonical executable payload is the validated
PyInstaller 5.7 `onedir` tree at:

```text
dist/PixelScope/
```

P7-B must consume that tree. ZIP creation and installer compilation must not rebuild
PixelScope or resolve a second dependency set.

The canonical version authority remains:

```text
src/pixelscope/version.py::__version__
```

Distribution names and installer metadata must derive from that value.

## Artifact names and lineage

P7-B generated output lives under ignored `release/` and uses the canonical stem:

```text
PixelScope-<version>-windows-x64
```

The expected outputs are:

```text
release/PixelScope-<version>-windows-x64.manifest.json
release/PixelScope-<version>-windows-x64-THIRD_PARTY_NOTICES.txt
release/PixelScope-<version>-windows-x64-portable.zip
release/PixelScope-<version>-windows-x64-setup.exe
```

The manifest records sorted relative paths, sizes, and SHA-256 digests for every file
in the validated `dist/PixelScope/` payload. Portable ZIP and installer staging must
ship that same manifest so later validation can prove both distribution forms descend
from the same onedir content.

## Portable ZIP contract

The portable archive contains one versioned top-level directory. Its application
payload is byte-for-byte the validated `dist/PixelScope/` tree, plus distribution-only
metadata files:

```text
PixelScope-<version>-windows-x64/
    PixelScope.exe
    ... canonical onedir payload ...
    release-manifest.json
    THIRD_PARTY_NOTICES.txt
```

ZIP creation must be deterministic with sorted paths and fixed member timestamps.
Portable smoke validation extracts to a temporary directory, validates the manifest
and onedir structure, then runs the real packaged executable through the P7-A smoke
harness.

## Installer contract

The installer is an Inno Setup installer for the existing Windows x64 application.
P7-B intentionally uses Inno Setup 6-compatible script syntax and does not require
Inno Setup 7-only directives as part of this slice.

Repository policy:

- target: Windows 10/11 x64;
- per-user install under `{localappdata}\Programs\PixelScope`;
- `PrivilegesRequired=lowest`; normal installation does not require administrator
  rights;
- stable, non-versioned `AppId` so a newer PixelScope installer upgrades the existing
  installation rather than creating a parallel product identity;
- 64-bit install mode for the x64 application;
- Start Menu shortcut only; no automatic desktop shortcut and no file association;
- installer does not launch PixelScope automatically after install;
- uninstall removes installed application/distribution files but does not delete
  PixelScope QSettings/user state;
- no signing tool, certificate, key, or production signing claim in P7-B.

PixelScope configures QApplication organization/application names as
`PixelScope`/`PixelScope` and persists preferences through QSettings outside the
application install directory. The installer therefore must not add registry cleanup
or user-data deletion rules for those settings.

## Inno Setup compiler boundary

The active P7 plan does not specify an exact Inno Setup version. P7-B keeps its script
compatible with the Inno Setup 6 syntax baseline and accepts current major 6 or 7
compilers for owner/manual validation. Compiler discovery remains external to the
Python release environment. The build script:

- accepts an explicit `--iscc` path or `ISCC_PATH` environment override;
- otherwise discovers common Inno Setup 6/7 install locations / PATH;
- verifies the compiler reports a supported major before compiling;
- invokes `ISCC.exe` directly and fails on a non-zero compile exit.

P7-C owns the exact hosted Inno Setup version pin when Windows CI is introduced. This
avoids inventing a local exact-version contract before the hosted toolchain exists.

## Third-party notice boundary

P7-B creates a distribution notice payload from the isolated release environment rather
than copying arbitrary development-environment packages. The notice generator records:

- the CPython runtime license from the release interpreter installation;
- installed release-environment distribution name/version/license metadata;
- license/copying/notice files shipped by those installed distributions.

Direct runtime dependencies from `requirements/runtime.txt` are required to be present
in the release environment. Missing release metadata or a missing Python runtime
license is a build error. The generated notice is compliance inventory evidence, not a
substitute for final corporate legal/release-policy approval; final policy closeout
remains P7-E.

## Installer smoke boundary

The installer smoke harness must use a temporary per-user install directory and perform:

```text
setup.exe /VERYSILENT ... /DIR=<temporary path>
    -> validate installed onedir + manifest/notices
    -> run real installed PixelScope.exe smoke
    -> unins000.exe /VERYSILENT ...
    -> verify application payload was removed
```

This proves compile/install/run/uninstall mechanics without introducing a test-only
application mode. The smoke harness must not intentionally clear existing PixelScope
QSettings.

## Validation boundary

Source/unit validation cannot replace artifact evidence. P7-B closeout requires owner
Windows evidence for:

- normal repository checks;
- focused P7-B distribution tests;
- P7-A onedir build/validation at the exact artifact-affecting source state;
- portable ZIP build and portable smoke;
- Inno Setup compile;
- installer install/run/uninstall smoke.

If only tests/docs change after the final artifact-affecting commit, artifact evidence
may be reused only when review confirms those later commits cannot change distribution
contents.

## Non-goals

P7-B does not add:

- GitHub Actions hosted Windows build automation;
- GitHub Release publication;
- release tags or version bump policy;
- update checking or self-update;
- production code signing;
- SSO/authentication or SMB credential behavior;
- P5-G external-environment validation.
