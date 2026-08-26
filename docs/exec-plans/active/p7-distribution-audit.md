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

The expected production outputs are:

```text
release/PixelScope-<version>-windows-x64.manifest.json
release/PixelScope-<version>-windows-x64-THIRD_PARTY_NOTICES.txt
release/PixelScope-<version>-windows-x64-portable.zip
release/PixelScope-<version>-windows-x64-setup.exe
```

Automated installer smoke may additionally create the disposable intermediate
`PixelScope-<version>-windows-x64-smoke-setup.exe`; the smoke harness removes it after
execution and it is not a release artifact.

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
P7-B intentionally uses Inno Setup 6.1-compatible script syntax and does not require
Inno Setup 7-only directives as part of this slice.

Repository policy:

- target: Windows 10/11 x64;
- per-user install under `{localappdata}\Programs\PixelScope`;
- `PrivilegesRequired=lowest`; normal installation does not require administrator
  rights;
- stable, non-versioned production `AppId` so newer PixelScope installers reuse the
  same upgrade and uninstall lineage rather than creating a parallel product identity;
- 64-bit install mode for the x64 application;
- Start Menu shortcut only; no automatic desktop shortcut and no file association;
- interactive Setup Completed page offers the standard `Launch PixelScope` post-install
  checkbox; silent installs do not launch the application;
- an existing production installation is detected from the per-user uninstall
  registration and its installed `PixelScope.exe` Windows file version is compared with
  the canonical installer version;
- older installed version -> explicit upgrade confirmation, default Yes;
- same installed version -> explicit reinstall confirmation, interactive default No;
- newer installed version -> explicit downgrade warning, default No;
- silent/suppressed same-version reinstall and normal upgrade may continue, while a
  downgrade or unverifiable existing version is rejected by default;
- uninstall removes installed application/distribution files but does not delete
  PixelScope QSettings/user state;
- no signing tool, certificate, key, or production signing claim in P7-B.

PixelScope configures QApplication organization/application names as
`PixelScope`/`PixelScope` and persists preferences through QSettings outside the
application install directory. The installer therefore must not add registry cleanup
or user-data deletion rules for those settings.

## Inno Setup compiler boundary

The installer uses packed-version Pascal support functions introduced in Inno Setup
6.1.0, so P7-B supports `>=6.1,<8` for owner/manual validation. In the supported
corporate environment, `ISCC.exe` and `Compil32.exe` PE version metadata may report
`0.0.0.0`; file metadata is therefore not treated as a reliable compiler-version
authority.

The Python build script uses `ISCC.exe /?` only to verify that the selected executable
is an Inno Setup command-line compiler from supported major family 6 or 7. The exact
version gate is owned by the canonical `.iss`, which checks Inno's predefined
`Ver`/`PREPROCVER` value at compile time and aborts when `Ver < 0x06010000` or
`Ver >= 0x08000000`. Thus 6.0.x cannot produce an installer even though its command-line
banner identifies only major 6.

Compiler discovery remains external to the Python release environment. The build script:

- accepts an explicit `--iscc` path or `ISCC_PATH` environment override;
- otherwise discovers common Inno Setup 6/7 install locations / PATH;
- verifies the command-line compiler major from its `/?` help banner;
- invokes `ISCC.exe` directly and fails on a non-zero compile exit, including an exact
  version-range rejection from the `.iss` `Ver` guard.

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

Automated installer smoke must remain repeatable even when the developer keeps the real
PixelScope installation installed. The smoke therefore compiles the same canonical
`packaging/installer/pixelscope.iss` recipe and consumes the same `dist/PixelScope/`
payload, but injects a dedicated disposable smoke `AppId`. The production stable AppId
remains the default and is unchanged for the release installer.

The smoke build also suppresses the production Start Menu shortcut so it cannot replace
or remove the user's real PixelScope shortcut. Existing-version production prompts are
bypassed only for the disposable smoke identity. Production AppId/version behavior is
covered by static contract tests plus owner interactive validation.

The installer smoke harness uses a temporary per-user install directory and performs:

```text
build same .iss with disposable smoke AppId
    -> setup.exe /VERYSILENT ... /DIR=<temporary path>
    -> require disposable uninstall registration
    -> validate installed onedir + manifest/notices
    -> run real installed PixelScope.exe smoke
    -> unins000.exe /VERYSILENT ...
    -> verify full manifest-owned payload removed
    -> verify manifest/notices and Inno unins* files removed
    -> verify disposable uninstall registration removed
    -> verify temporary PixelScope install directory removed
    -> delete disposable smoke setup.exe
```

The launch checkbox is skipped in silent mode. The smoke harness must not intentionally
clear existing PixelScope QSettings. A stale disposable smoke registration is treated
as a failed precondition rather than being silently overwritten.

This proves compile/install/run/uninstall mechanics without requiring the production
PixelScope installation to be removed from the development machine. Final production
stable-AppId clean-PC qualification remains P7-E.

## Validation boundary

Source/unit validation cannot replace artifact evidence. P7-B closeout requires owner
Windows evidence for:

- normal repository checks;
- focused P7-B distribution tests;
- P7-A onedir build/validation at the exact artifact-affecting source state;
- portable ZIP build and portable smoke;
- production Inno Setup compile;
- disposable-AppId installer install/run/uninstall smoke;
- interactive production installer confirmation for existing-version and post-install
  launch UX.

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
