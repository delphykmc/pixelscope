# Packaging constraints

- The Windows release build environment is CPython `>=3.10.8,<3.11` x64.
- The executable builder is **exactly `PyInstaller==5.7`**.
- PyInstaller 6.x is prohibited by internal security and installation policy,
  not merely discouraged.
- The canonical executable build is PyInstaller `onedir`. Do not switch to `onefile`.
- Release/build-only dependencies live in `requirements/release.txt`; PyInstaller is
  not an application runtime dependency. The PyInstaller 5.7-era hook/tool dependency
  set is pinned rather than resolved to arbitrary future releases.
- The release version authority is
  `src/pixelscope/version.py::__version__`. Python package metadata, executable
  metadata, ZIP/installer names, release tag/title, candidate provenance, and
  publication metadata must derive from it.
- The canonical PyInstaller spec is `packaging/pixelscope.spec` and reuses
  `src/pixelscope/__main__.py`, which delegates to the existing
  `pixelscope.app.application.main` composition root. Do not add a second application
  bootstrap for packaging.
- Canonical generated paths are `build/pyinstaller/` for PyInstaller work files,
  `build/release/` for generated executable metadata, `dist/PixelScope/` for the
  validated `onedir` tree, and ignored `release/` for distribution/candidate/publication
  staging artifacts. Generated release output must not be written into
  `src/pixelscope/`.
- `scripts/build_release.py` is the canonical Windows executable build entry. It
  rejects non-Windows, non-x64, Python outside `>=3.10.8,<3.11`, and PyInstaller
  versions other than 5.7; it generates executable version metadata, runs the spec,
  and then runs structural artifact validation.
- `scripts/validate_release_artifact.py` validates the canonical onedir structure,
  application icon resources, Python/Qt/PySide6/NumPy/OpenCV runtime components, and
  absence of top-level source/dev-tree leakage.
- `scripts/smoke_packaged_release.py` is the Windows executable smoke harness. It
  launches the real `PixelScope.exe`, waits for the process-owned visible PixelScope
  window, requests normal close, and requires bounded clean termination. It does not
  add test-only behavior to the production application.
- In a normal source run, failure to read/decode the application icon remains a warning
  with the existing empty-icon fallback. In a PyInstaller frozen process, the canonical
  application icon is a required core packaged resource: read/decode failure aborts
  startup. Therefore a PASSing packaged executable smoke proves both application
  startup and successful runtime resolution/decode of the icon through
  `importlib.resources`.
- Portable ZIP and Inno Setup installer must consume the same validated
  `dist/PixelScope/` tree rather than rebuilding the application independently.
- P7-B records that shared payload in a versioned SHA-256 manifest containing sorted
  relative paths, sizes, and digests. Portable and installed distributions include
  that manifest plus `THIRD_PARTY_NOTICES.txt` as distribution-only metadata.
- P7-B portable ZIP creation is deterministic for identical input payloads: archive
  paths are sorted and ZIP member timestamps are fixed.
- P7-B uses Inno Setup APIs introduced in 6.1.0 and therefore supports local/manual
  installer compilation with **Inno Setup `>=6.1,<8`**. `ISCC.exe` PE version metadata
  is not a reliable compiler-version authority in the supported corporate environment
  and may legitimately report `0.0.0.0`. Python tooling therefore uses the `ISCC /?`
  banner only to identify a supported Inno command-line compiler major (6 or 7). The
  authoritative exact range check is the canonical `.iss` compile-time guard using
  Inno's own `Ver`/`PREPROCVER` value: `<6.1` and `>=8` abort compilation before setup
  generation. P7-C preserves this range and records the actual owner-local compiler
  executable name, major, and SHA-256 in release-candidate provenance rather than
  introducing a CI-only exact compiler pin or persisting local absolute tool paths.
- Installer scope is per-user/no-admin: `PrivilegesRequired=lowest`, install under
  `{localappdata}\Programs\PixelScope`, stable non-versioned production `AppId`, x64
  install mode, and a Start Menu shortcut. Do not silently switch to machine-wide/admin
  installation.
- Interactive installer completion offers a standard `Launch PixelScope` post-install
  checkbox. The entry uses Inno Setup `postinstall` semantics and is skipped for silent
  installs.
- Existing-install version UX derives from the installed `PixelScope.exe` Windows file
  version and the same canonical release-version components used for installer metadata:
  older -> explicit upgrade confirmation, same -> reinstall confirmation, newer ->
  downgrade warning. Interactive same-version and downgrade prompts default to No;
  upgrade defaults to Yes.
- Suppressed/silent production-installer behavior is fail-safe for downgrade or
  unverifiable existing versions. Same-version repair and normal upgrade may proceed
  without an interactive prompt.
- Automated installer smoke must be safe while a real PixelScope installation remains
  installed. It compiles the **same canonical `packaging/installer/pixelscope.iss`** and
  consumes the same `dist/PixelScope/` payload, but injects a dedicated disposable smoke
  `AppId`. The production stable AppId remains the default for release builds.
- The disposable smoke build suppresses the production Start Menu shortcut so it cannot
  replace or remove the real user's shortcut. It uses a distinct intermediate
  `PixelScope-<version>-windows-x64-smoke-setup.exe`, which is deleted after the smoke
  and is not a release artifact.
- Installer smoke must prove full cleanup, not only `PixelScope.exe` removal. After
  uninstall it verifies every manifest-owned payload file, `release-manifest.json`,
  `THIRD_PARTY_NOTICES.txt`, Inno-owned `unins*` files, the disposable smoke uninstall
  registration, and the temporary install directory are removed.
- Installer upgrade/uninstall must not intentionally delete PixelScope QSettings or
  other user state. The installer definition must not introduce settings-registry
  cleanup, file associations, credential handling, or unconditional post-install launch.
- Production signing remains deferred. P7 foundation must not commit certificates/keys,
  invoke a privileged production SignTool without an authoritative policy, or describe
  unsigned artifacts as signed.
- Third-party notices are generated from the isolated release environment. The payload
  includes the CPython runtime license plus installed release-environment package
  license metadata/files, and direct runtime requirements must be present. This is
  release inventory evidence, not final corporate legal approval.
- User configuration/data must live outside installed application resources.
- Resource lookup must not depend on the source tree or current working directory.
- Canonical application-icon assets live at
  `src/pixelscope/assets/icons/pixelscope.{svg,png,ico}` and are included as package
  data. Do not maintain a duplicate release icon elsewhere.
- `scripts/generate_icon_assets.py` is the supported path for deriving PNG and ICO from
  the canonical SVG. Asset generation uses the dev-pinned `resvg_py==0.3.3` and
  `Pillow==12.3.0`; those packages are build/development dependencies and are not
  required by the runtime application.
- `scripts/generate_icon_assets.py --check` must regenerate PNG/ICO into a temporary
  directory, compare them byte-for-byte with the checked-in canonical derivatives,
  fail on any mismatch, and clean the temporary output afterward.
- Runtime icon loading reads packaged PNG bytes through `importlib.resources`.
- Windows source runs assign `PixelScope.PixelScope` as the process AppUserModelID
  before `QApplication` creation, then assign the canonical icon to both `QApplication`
  and the main window. This source-run shell identity is a P2-A1 runtime requirement,
  not a substitute for packaged executable metadata.
- The Windows ICO contains transparent 16, 20, 24, 32, 40, 48, 64, 128, and 256 px
  frames. PyInstaller and Inno Setup use the same canonical ICO.
- A wheel/package-content smoke check must verify the SVG, PNG, and ICO are present and
  nonempty before an identity/resource PR is complete.
- Final installed-shell grouping, production signing, and final release publication
  remain later P7 work.
- Freeze the verified dependency set before packaging and do not change the lock during
  a packaging run.
- A clean Windows 10/11 PC smoke test is mandatory before final release.

## P7-A Windows validation

Create a release-only environment so release-tool pins do not alter the normal
repository development environment:

```powershell
py -3.10 -m venv .venv-release
.\.venv-release\Scripts\python.exe -m pip install -r requirements\release.txt
.\.venv-release\Scripts\python.exe scripts\build_release.py
.\.venv-release\Scripts\python.exe scripts\validate_release_artifact.py
.\.venv-release\Scripts\python.exe scripts\smoke_packaged_release.py
```

`scripts/build_release.py` already invokes structural artifact validation after a
successful PyInstaller build. Running the validator explicitly afterward is retained
as a clear owner/reviewer evidence step.

## P7-B Windows validation

P7-B uses the already-isolated `.venv-release` for Python release tooling and an
external supported Inno Setup installation for installer compilation.

```powershell
# focused distribution contract
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_release_distribution.py

# rebuild/validate canonical onedir when artifact-affecting source changed
.\.venv-release\Scripts\python.exe scripts\build_release.py
.\.venv-release\Scripts\python.exe scripts\validate_release_artifact.py

# third-party notices + deterministic portable ZIP + real portable smoke
.\.venv-release\Scripts\python.exe scripts\build_third_party_notices.py
.\.venv-release\Scripts\python.exe scripts\build_portable_release.py
.\.venv-release\Scripts\python.exe scripts\smoke_portable_release.py

# Inno Setup >=6.1,<8 compiler can be found from PATH/common install paths,
# supplied with ISCC_PATH, or supplied explicitly with --iscc. Exact range
# enforcement happens inside the canonical .iss using the compiler's Ver value.
.\.venv-release\Scripts\python.exe scripts\build_installer_release.py
.\.venv-release\Scripts\python.exe scripts\smoke_installer_release.py
```

For interactive validation, also verify that the Setup Completed page offers `Launch
PixelScope`, and that rerunning Setup detects the existing installation and asks for
reinstall/upgrade/downgrade confirmation according to version ordering.

Expected P7-B outputs derive from the canonical version, for example at `0.1.0`:

```text
release/PixelScope-0.1.0-windows-x64.manifest.json
release/PixelScope-0.1.0-windows-x64-THIRD_PARTY_NOTICES.txt
release/PixelScope-0.1.0-windows-x64-portable.zip
release/PixelScope-0.1.0-windows-x64-setup.exe
```

Windows evidence is artifact-state evidence. If source, packaging scripts/specs,
release requirements, installer files, or distribution tooling change after a PASS,
re-run the applicable build/smoke validation rather than carrying stale evidence
forward. Test/docs-only commits may reuse artifact evidence only when review confirms
they cannot alter generated distribution contents.

## P7-C owner-local Release Candidate Build & Validation

P7-C has no mandatory GitHub-hosted or self-hosted runner. The canonical
release-candidate entry point is `scripts/build_release_candidate.py`, executed by the
authorized owner on the Windows development PC after the candidate source commit is
selected.

Default environment split:

```text
.venv\Scripts\python.exe          # docs/tests/ruff/mypy/repository validation
.venv-release\Scripts\python.exe  # PyInstaller/distribution build + artifact smoke
```

The entry point accepts `--dev-python`, `--release-python`, and `--iscc` when explicit
paths are required. It resolves one supported Inno Setup compiler under the existing
P7-B `>=6.1,<8` contract, reuses that compiler for production installer build and
smoke, and records the compiler executable name/major/SHA-256 in provenance. It does
not persist local absolute Python/Inno paths and does not download or install an Inno
compiler from the network.

The owner-local command is:

```powershell
.\.venv\Scripts\python.exe scripts\build_release_candidate.py
```

or, when an explicit compiler is desired:

```powershell
.\.venv\Scripts\python.exe scripts\build_release_candidate.py `
    --iscc "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

The command requires a clean source worktree and fails immediately when any repository,
build, smoke, or bundle-validation step fails. It reuses the P7-A/P7-B scripts rather
than maintaining a second packaging implementation.

`scripts/validate_release_bundle.py` requires the generated `release/` root to contain
exactly the four current-version production distribution files, rejects missing/extra
or empty files and disposable smoke installers, and revalidates the payload manifest
against `dist/PixelScope/`.

After bundle validation succeeds, the candidate is staged under:

```text
release/candidate/PixelScope-<version>-windows-x64/
```

with the four validated production artifacts plus `release-provenance.json` and a
rendered `RELEASE_NOTES.md`. `scripts/release_candidate_contract.py` is the executable
P7-C provenance authority. Candidate writing and P7-D reading use the same exact schema:
all current fields are required, unknown fields are rejected, tool executable identities
are basenames rather than local paths, `release_note_source` is repository-relative,
Git/SHA-256 identities are canonical, and the artifact map must exactly match the staged
production files. Provenance records the canonical version, exact source commit, build
timestamp, release Python executable name/version, PyInstaller version, actual Inno
compiler executable name/major/SHA-256, release-note source, and artifact SHA-256
inventory without local absolute machine paths.

The durable current release-note source is
`docs/releases/2026-08-26-v0.1.0.md`; the candidate command renders the exact source
commit into its staged copy.

Repository automation stops at candidate preparation. Production GitHub Release upload,
restricted-folder transfer/publication, and signing credentials are beyond this
automation authority and require an authorized human procedure. Manual authorized
publication is a supported production path, not a fallback failure.

## P7-D Stage 1 Release Metadata & Manual Publication Foundation

P7-D Stage 1 consumes the canonical P7-C candidate. It does **not** rebuild the
application, redefine the strict four-file P7-C production bundle, or re-specify the
candidate provenance schema.

Provider-neutral publication staging is prepared under:

```text
release/publication/PixelScope-<version>-windows-x64/
```

It contains exact copies of the candidate's four production artifacts,
`RELEASE_NOTES.md`, `release-provenance.json`, plus
`release-publication.json`. The publication metadata derives from the same canonical
version and records only provider-neutral identity/provenance: product, target, version,
`v<version>` release tag, `PixelScope v<version>` release title, exact source commit,
release-note identity/hash, candidate-provenance identity/hash, and exact production
artifact sizes/SHA-256 values.

The canonical commands are:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_release_publication.py
.\.venv\Scripts\python.exe scripts\validate_release_publication.py
```

Immediately before authorized publication, after the canonical tag exists locally, the
exact local tag/source relationship may also be checked without creating or pushing a
tag:

```powershell
.\.venv\Scripts\python.exe scripts\validate_release_publication.py --require-tag
```

The tag contract is `v<canonical-version>` and it must resolve to the exact
`source_commit` recorded by candidate provenance. Repository tooling validates but does
not create/push the production tag.

Publication preparation requires the current checkout commit to equal candidate
provenance, replaces stale same-version publication staging, and validates exact copies
and metadata hashes. It never creates a GitHub Enterprise Release, uploads assets,
transfers restricted files, uses credentials, or performs signing.

Publication metadata and copied candidate provenance must not contain credentials,
access tokens, browser cookies, local absolute tool paths, corporate secrets, or an
unnecessary hard-coded corporate GitHub host/repository URL. The exact shared P7-C
provenance schema prevents arbitrary extra/private fields from crossing through the
copied `release-provenance.json`.

Actual corporate GitHub Enterprise Release creation and approved asset upload remain an
authorized human action across the corporate security boundary. After publication, the
authorized procedure must verify that the remote corporate release/tag resolves to the
same exact candidate provenance `source_commit`, then verify uploaded asset filename/
hash identity and release visibility/access. The local `--require-tag` check does not
replace this remote-side post-publication verification.

## Notification-only update discovery — deferred P7-D Stage 2

Runtime update discovery is not part of Stage 1. The governing rule is:

> **Update discovery must never initiate authentication.**

Stage 1 does not establish whether the eventual authoritative provider requires
application authentication. If it does, a future implementation may use only an
already-established approved P6 capability and otherwise skips discovery silently. If
an authoritative provider is explicitly usable without application authentication,
that path remains permitted.

Stage 1 establishes no common-IdP topology and selects no OAuth App, GitHub App, PAT,
bearer-token reuse, token exchange, browser-cookie reuse, or update metadata provider.
Those choices remain P6/P7-D Stage 2 work after the relevant provider/access contracts
are authoritative.
