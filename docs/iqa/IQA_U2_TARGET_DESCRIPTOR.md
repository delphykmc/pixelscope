# Issue #156 U2 — caller-selected packaging target

PUBLIC MAIN retains its Core/Reference build commands and does not ship a
PRIVATE SUB/Full package. PRIVATE SUB owns its descriptor, PyInstaller spec,
real launcher, runtime dependency inventory and installer release approval.
A PRIVATE SUB descriptor MUST live outside replaceable handoff-owned
enterprise/iqa/** leaves, e.g. internal_packaging/pixelscope-full.json.
The CLI option --target-descriptor selects a specific descriptor file;
no private files are read by the public Core/Reference default builds.

## Descriptor shape

The following is an **illustrative** descriptor; referenced private files
do not exist in PUBLIC MAIN and the example GUID is NOT a production identity:

~~~json
{
  "schema_version": 1,
  "target_id": "full",
  "spec": "internal_packaging/pixelscope-full.spec",
  "app_dir": "PixelScopeFull",
  "executable": "PixelScopeFull.exe",
  "display_name": "PixelScope Full",
  "installer_app_id": "{A33A81AB-5B0B-4249-8314-ABACBDF45990}",
  "smoke_window_title": "PixelScope Full",
  "runtime_requirements": "internal_packaging/runtime-requirements.txt"
}
~~~

Spec and optional additional runtime requirements paths must exist within
the checkout and are resolved relative to repository root. The descriptor
JSON location is caller-selected (even outside the repository). Unknown
schema fields, escape/traversal, absolute/drive paths, name collisions with
Core/Reference and unsafe names are rejected. The private spec is responsible
for the EXACT output app_dir/executable and must consume generated version
metadata at build/release/<app_dir>.version.txt. The generated bundle must
retain public offline Help/icon and native dependency layout.

## Windows release + smoke flow

Run under isolated Windows x64 CPython >=3.10.8,<3.11, pinned PyInstaller
5.7 and supported Inno Setup. The public scripts do NOT install private
dependencies, generate private launchers or authorize an internal server.

~~~powershell
$target = "internal_packaging/pixelscope-full.json"

& $py scripts/build_release.py --target-descriptor $target
& $py scripts/validate_release_artifact.py --target-descriptor $target
& $py scripts/smoke_packaged_release.py --target-descriptor $target
& $py scripts/build_portable_release.py --target-descriptor $target
& $py scripts/smoke_portable_release.py --target-descriptor $target
& $py scripts/build_installer_release.py --target-descriptor $target
& $py scripts/smoke_installer_release.py --target-descriptor $target
& $py scripts/validate_release_bundle.py --target-descriptor $target
~~~

Default public Core executable/artifact stem remains PixelScope;
custom output stems are <app_dir>-<version>-windows-x64.
Release manifest product/payload_root and ZIP archive root are matched
against descriptor-selected app identity and SHA-256 payload inventory.
Installer smoke uses a disposable registry identity and removes installed
files; smoke requires a GUI/window title match and is Windows-local, not
headless hosted CI. The public build_release_candidate.py remains the
Core P7-C publication pipeline; INTERNAL provenance/release candidate
orchestration and security approval stay PRIVATE SUB-owned.

The optional runtime_requirements file lists private packages that must
exist in the isolated release environment with discoverable license metadata.
Public third-party notices include all installed packages; PRIVATE SUB
must separately validate full dependency pins, entrypoints, transitive
license terms, SBOM, installer trust/signature and proprietary provenance.
PUBLIC requirements/runtime.txt and pyproject entrypoints stay unchanged.

## Public synthetic test gate (not a real build)

~~~powershell
& $py -m pytest -q tests/unit/test_release_target_descriptor.py tests/unit/test_release_packaging.py tests/unit/test_release_distribution.py
& $py -m ruff check .
& $py -m ruff format --check .
& $py -m mypy src
~~~

These are synthetic third-target descriptor, Inno command, portable and
manifest/bundle validation checks, not real PyInstaller/ISCC release smoke.
The SUB owner must run full packaging on an authorized Windows host using
a real private spec, with public MAIN/handoff/SUB exact SHA pinning.
