# Issue #156 U9 — PRIVATE SUB-owned Full packaging integration

Status: **PUBLIC-safe integration/acceptance instructions**, not a working
PRIVATE SUB executable, a confidential launcher, or a production release
approval. This document complements [the U2 descriptor contract](IQA_U2_TARGET_DESCRIPTOR.md). The generic U2 plumbing was merged into
PUBLIC `main` by [PR #167](https://github.com/delphykmc/pixelscope/pull/167)
at exact `4a85285c49bb97d90f92fdb6edfc81702242a269`. Any SUB integration
must pin and verify the actual MAIN SHA selected for its release.

## Ownership: no permanent fork of MAIN's package definitions

| Component | Owner | Where it belongs |
| --- | --- | --- |
| `scripts/build_release.py`, portable/installer/smoke tools, generic descriptor validator | PUBLIC MAIN | Inherited, **do not patch in SUB** |
| `pyproject.toml`, `requirements/runtime.txt`, `requirements/release.txt` | PUBLIC MAIN | Unchanged Core/Reference defaults |
| Real Full Python process launcher/entry point | PRIVATE SUB | Downstream-owned source; **not** a new MAIN `[project.scripts]` entry |
| Full PyInstaller `.spec` with exact `EXE`/`COLLECT` identity | PRIVATE SUB | Outside replaceable Handoff IQA leaves |
| Full JSON target descriptor and separate pinned build requirements | PRIVATE SUB | Caller-selected path, outside replaceable Handoff IQA leaves |
| Runtime-only distribution-name inventory for notice audit | PRIVATE SUB | Descriptor's optional `runtime_requirements` file |
| Provider auth, server URLs, private storage, keys, build secrets | PRIVATE SUB | Never in public code, docs, GitHub comments or Handoff |
| QA on the actual Full binary, installer signing, SBOM, license/legal review | PRIVATE SUB | Internal acceptance/evidence system |

For illustration only, PRIVATE SUB could own:

```text
internal_packaging/
  pixelscope-full.json
  pixelscope-full.spec
  full_launcher.py
  private-release.lock
  runtime-requirements.txt
```

These are **illustrative filenames**, not files in PUBLIC MAIN or Handoff.
They must be owned by PRIVATE SUB, protected according to company policy,
and excluded from allowlisted Handoff add/update/delete operations. The
Handoff transfer leaves `src/pixelscope_enterprise/iqa/**`,
`tests/enterprise/iqa/**`, `docs/enterprise/iqa/**` and
`enterprise/iqa/**` are replaceable at import time; avoid keeping a
private packaging source or installer identity underneath those leaves.

## Build entry point: the private PyInstaller spec owns it

The PUBLIC U2 builder invokes `python -m PyInstaller --clean --noconfirm`
with the **exact `spec` field** supplied by the validated descriptor.
It does **not** use `pyproject.toml` console scripts to pick the downstream
executable. Therefore PRIVATE SUB should supply its own Python launcher
and `.spec` without editing MAIN-owned package metadata.

The private launcher is responsible for authorized IQA composition and
shutdown via the MAIN public host and Handoff extension hooks. Do not
copy the PUBLIC Core spec verbatim: that spec deliberately excludes
`pixelscope_enterprise` and uses the Core launcher. In a Full spec:

1. Set `Analysis` to the authorized PRIVATE SUB launcher and explicit
   private/public source search roots. Configure allowed hidden imports,
   Qt/native binaries, icons and validated runtime resources for the
   final executable. Never embed authentication secrets in source or spec.
2. Use exactly the descriptor's `app_dir` for `COLLECT(name=...)` and
   the matching executable stem for `EXE(name=...)`. Example: if
   `app_dir=PixelScopeFull`, then the frozen executable must be
   `PixelScopeFull.exe` under `dist/PixelScopeFull/`.
3. Consume `build/release/<app_dir>.version.txt` emitted by U2 immediately
   before PyInstaller. Preserve the standard icon assets, Qt platform
   plugin, Python/NumPy/OpenCV shared libraries and offline Help layout
   expected by `validate_release_artifact.py`.
4. Arrange the **actual Full GUI window title** to contain the descriptor's
   `smoke_window_title` without lying about readiness. A smoke can start
   and close the GUI, but it cannot certify server permissions or model
   science.
5. Do not rely on a previous output tree: the U2 custom build deliberately
   precleans only `dist/<app_dir>`, then requires a fresh nonempty
   `<executable>` before copying Help/validating. Protect any output
   you must retain elsewhere.

The real `.spec` and launcher are security-sensitive downstream code and
must be implemented/reviewed within PRIVATE SUB. This PUBLIC document
intentionally contains no copy-paste substitute for them.

## Dependencies and third-party notices are distinct responsibilities

**Install/build set:** PRIVATE SUB owns an isolated Windows x64 Python
3.10.8+ (and <3.11) release environment. It should install MAIN's exact
`requirements/release.txt` and a separate PRIVATE SUB-pinned dependency
set such as `internal_packaging/private-release.lock`; do not modify
MAIN's `requirements/runtime.txt` or `pyproject.toml`. Verify
`python -m pip check` plus internal version/hash/approved-index policies.

**Notice-audit inventory:** the descriptor's optional
`runtime_requirements` property points to an **existing repo-relative
`.txt` file** that lists additional distributions required at runtime.
Use one simple nonsecret distribution requirement per noncomment line.
The PUBLIC notice auditor currently extracts **distribution names**,
checks they are installed in the active environment and have discoverable
license metadata/files, and emits an inventory for all installed
distributions. This is **not** a lockfile parser, wheel build-time
dependency resolver, pinned-version comparison, complete recursive SBOM,
license grant, or approval. `-r`, `-e`, option directives and URL
requirements are not accepted in this notice-specific input. Keep the
complete private lock/dependency installation logic in SUB; maintain the
flat notice inventory separately.

Run the notice generator against the explicitly selected target:

```powershell
$target = "internal_packaging/pixelscope-full.json"
& $py scripts/build_third_party_notices.py --target-descriptor $target
```

Inspect the generated Target-specific notices and reconcile them against
the **actual frozen binary's** native/non-Python dependencies, licensing
and security attestations. Never publish a private package-name inventory
to a PUBLIC repository if its content is sensitive.

## PRIVATE SUB Windows smoke and release checklist

Do this in the **authorized PRIVATE SUB checkout** after importing an
exact, approved MAIN SHA and the approved Handoff files via the U3/U11
manifest. A file called `internal_packaging/pixelscope-full.json` does
not exist in PUBLIC MAIN. In the PowerShell session, set `$py` to the
real release interpreter for that checkout (a quoted executable path
must be invoked with `&`).

```powershell
$py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$target = "internal_packaging/pixelscope-full.json"
if (-not (Test-Path $target)) { throw "Missing PRIVATE SUB target descriptor" }

# Preflight: strictly validate descriptor paths/identity without building.
& $py -c "from pathlib import Path; from scripts.package_target_descriptor import load_target_descriptor; print(load_target_descriptor(Path('$target')))"
if ($LASTEXITCODE -ne 0) { throw "Target descriptor rejected" }

# Actual U2/PRIVATE SUB native pipeline (do not run on PUBLIC MAIN).
& $py scripts/build_release.py --target-descriptor $target
if ($LASTEXITCODE -ne 0) { throw "Full PyInstaller build failed" }
& $py scripts/validate_release_artifact.py --target-descriptor $target
if ($LASTEXITCODE -ne 0) { throw "Full onedir validator failed" }
& $py scripts/smoke_packaged_release.py --target-descriptor $target
if ($LASTEXITCODE -ne 0) { throw "Full executable smoke failed" }
& $py scripts/build_portable_release.py --target-descriptor $target
if ($LASTEXITCODE -ne 0) { throw "Full portable archive build failed" }
& $py scripts/smoke_portable_release.py --target-descriptor $target
if ($LASTEXITCODE -ne 0) { throw "Full portable smoke failed" }
& $py scripts/build_installer_release.py --target-descriptor $target
if ($LASTEXITCODE -ne 0) { throw "Full Inno build failed" }
& $py scripts/smoke_installer_release.py --target-descriptor $target
if ($LASTEXITCODE -ne 0) { throw "Full installer install/uninstall failed" }
& $py scripts/validate_release_bundle.py --target-descriptor $target
if ($LASTEXITCODE -ne 0) { throw "Full release bundle validation failed" }
```

**Verify separately** that the installed Full registry AppId matches
the approved, **non-PUBLIC** GUID and that the installer smoke removes
all disposable resources. Retain actual full process-exit status,
logs, artifacts, binary provenance, offline GUI/help evidence,
dependency-license/SBOM review, code signing policy, and approved
PRIVATE SUB runtime integration evidence. The eight commands above
do not prove a real authenticated request/result round trip on their
own; that is PRIVATE SUB provider/result integration acceptance.

## Import/freeze handoff sequence and what is not yet done

- U2 PUBLIC MAIN merged; U9 PUBLIC-safe integration guidance does **not**
  mean the downstream descriptor/spec/launcher or locked dependencies
  have been written. Their implementation and tests are PRIVATE SUB-owned.
- Handoff development merges (U3/U11, U5/U6, U7, UX slices) are **not**
  immutable approved tags. Approval requires exact SHA, protected tag,
  externally authenticated manifest with per-path operations, native
  Windows test evidence and explicit review. Later frozen Handoff SHAs
  must descend from earlier approved SHAs.
- Run Handoff's
  `docs/enterprise/iqa/IQA_U7_VALIDATION_MATRIX.md` owner/local tests
  on the exact handoff snapshot before a security transfer, not on an
  unrelated temporary feature branch.
- PRIVATE SUB then imports only explicitly allowlisted Handoff IQA paths,
  preserving unrelated siblings and the private packaging tree. Record
  `MAIN_SHA`, approved `HANDOFF_SHA`/manifest digest/tag and
  `SUB_SHA` separately, with the runtime contract revision.
- Do not merge `src/pixelscope_enterprise/**` or PRIVATE SUB packaging
  files into PUBLIC MAIN. Do not claim Full end-to-end smoke, release
  authorization or successful import from the public synthetic CI alone.
