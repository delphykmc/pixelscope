"""Issue #156 U2: synthetic third-target distribution end-to-end contract."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import build_portable_release as portable
from scripts import build_release as release_builder
from scripts import build_third_party_notices as notices
from scripts.build_installer_release import installer_command
from scripts.build_release import pyinstaller_command
from scripts.distribution_contract import (
    DistributionValidationError,
    build_payload_manifest,
    installer_path,
    manifest_path,
    notice_path,
    portable_zip_path,
    release_stem,
    validate_payload_manifest,
    write_payload_manifest,
)
from scripts.package_target_descriptor import load_target_descriptor
from scripts.release_contract import (
    release_version,
    render_windows_version_info,
    windows_version_tuple,
)
from scripts.validate_release_bundle import validate_release_bundle


def _descriptor_file(tmp_path: Path, **overrides: object) -> Path:
    content: dict[str, object] = {
        "schema_version": 1,
        "target_id": "full-synthetic",
        "spec": "packaging/pixelscope.spec",
        "app_dir": "PixelScopeSynthetic",
        "executable": "PixelScopeSynthetic.exe",
        "display_name": "PixelScope Synthetic",
        "installer_app_id": "{A33A81AB-5B0B-4249-8314-ABACBDF45990}",
        "smoke_window_title": "PixelScope Synthetic",
    }
    content.update(overrides)
    path = tmp_path / "caller-owned" / "target.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_caller_selected_descriptor_drives_spec_exe_version_inno(tmp_path: Path) -> None:
    path = _descriptor_file(tmp_path)
    target = load_target_descriptor(path)
    assert path.is_file()
    assert target.target_id == "full-synthetic"
    assert target.output_root.name == "PixelScopeSynthetic"
    assert pyinstaller_command(descriptor=target)[-1] == str(target.spec)
    assert release_stem("1.2.3", descriptor=target) == ("PixelScopeSynthetic-1.2.3-windows-x64")
    assert manifest_path("1.2.3", descriptor=target).name.startswith("PixelScopeSynthetic")
    assert notice_path("1.2.3", descriptor=target).name.startswith("PixelScopeSynthetic")
    assert portable_zip_path("1.2.3", descriptor=target).name.startswith("PixelScopeSynthetic")
    assert installer_path("1.2.3", descriptor=target).name.startswith("PixelScopeSynthetic")

    rendered = render_windows_version_info(
        "1.2.3",
        identity=(target.app_dir, target.executable, target.display_name),
    )
    assert 'StringStruct("OriginalFilename", "PixelScopeSynthetic.exe")' in rendered
    command = installer_command(Path("C:/Inno/ISCC.exe"), descriptor=target)
    assert f"-dTargetAppName={target.display_name}" in command
    assert f"-dTargetExeName={target.executable}" in command
    assert f"-dTargetAppSource={target.output_root}" in command
    assert "-dAppIdValue={{A33A81AB-5B0B-4249-8314-ABACBDF45990}" in command
    assert "-dTargetRegistryAppId={A33A81AB-5B0B-4249-8314-ABACBDF45990}" in command

    assert Path(pyinstaller_command()[-1]).name == "pixelscope.spec"
    assert Path(pyinstaller_command("reference")[-1]).name == "pixelscope-reference.spec"
    assert release_stem("1.2.3") == "PixelScope-1.2.3-windows-x64"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"schema_version": 2}, "schema"),
        ({"schema_version": True}, "schema"),
        ({"target_id": "core"}, "target_id"),
        ({"spec": "../hidden/secret.spec"}, "unsafe"),
        ({"spec": "/private/secret.spec"}, "unsafe"),
        ({"app_dir": "PixelScope"}, "overwrite"),
        ({"app_dir": "CON"}, "reserved device"),
        ({"app_dir": "com1"}, "reserved device"),
        ({"app_dir": "LPT9"}, "reserved device"),
        ({"app_dir": "Bad\\Path"}, "app_dir"),
        ({"executable": "../bad.exe"}, "executable"),
        ({"display_name": 'Bad"Injected'}, "display_name"),
        ({"installer_app_id": "not-a-guid"}, "GUID"),
        ({"installer_app_id": "{6fa0ab08-ab41-4f77-93e8-16ce6ff53e5c}"}, "collides"),
        ({"runtime_requirements": "../secret.txt"}, "unsafe"),
        ({"unexpected_key": "x"}, "unknown"),
    ],
)
def test_descriptor_rejects_invalid_or_unsafe_values(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        load_target_descriptor(_descriptor_file(tmp_path, **overrides))


def test_issue176_opt_ins_are_absent_by_default_and_validated(tmp_path: Path) -> None:
    ordinary = load_target_descriptor(_descriptor_file(tmp_path))
    assert ordinary.supersedes_installer_app_ids == ()
    assert ordinary.release_revision is None

    selected = load_target_descriptor(
        _descriptor_file(
            tmp_path,
            supersedes_installer_app_ids=["{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}"],
            release_revision=65535,
        )
    )
    assert selected.supersedes_installer_app_ids == ("{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}",)
    assert selected.release_revision == 65535
    assert (
        load_target_descriptor(_descriptor_file(tmp_path, release_revision=0)).release_revision == 0
    )


@pytest.mark.parametrize(
    ("fields", "error"),
    [
        ({"supersedes_installer_app_ids": []}, "nonempty list"),
        ({"supersedes_installer_app_ids": "not-a-list"}, "nonempty list"),
        ({"supersedes_installer_app_ids": [1]}, "GUID"),
        ({"supersedes_installer_app_ids": ["6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C"]}, "GUID"),
        (
            {"supersedes_installer_app_ids": ["{A33A81AB-5B0B-4249-8314-ABACBDF45990}"]},
            "self-supersession",
        ),
        (
            {"supersedes_installer_app_ids": ["{AA3A81AB-5B0B-4249-8314-ABACBDF45990}"]},
            "allowlisted",
        ),
        (
            {
                "supersedes_installer_app_ids": [
                    "{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}",
                    "{6fa0ab08-ab41-4f77-93e8-16ce6ff53e5c}",
                ]
            },
            "duplicate",
        ),
        ({"release_revision": -1}, "release_revision"),
        ({"release_revision": 65536}, "release_revision"),
        ({"release_revision": True}, "release_revision"),
        ({"release_revision": None}, "release_revision"),
        ({"release_revision": "1"}, "release_revision"),
        ({"release_revision": 1.0}, "release_revision"),
    ],
)
def test_issue176_invalid_descriptor_opt_ins(
    tmp_path: Path, fields: dict[str, object], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        load_target_descriptor(_descriptor_file(tmp_path, **fields))


def test_issue176_four_part_revision_is_scoped_to_downstream(tmp_path: Path) -> None:
    ordinary = load_target_descriptor(_descriptor_file(tmp_path))
    revised = load_target_descriptor(_descriptor_file(tmp_path, release_revision=2))
    current = release_version()
    assert ordinary.effective_version == current
    assert revised.effective_version == f"{current}.2"
    assert release_stem(descriptor=ordinary).endswith(f"{current}-windows-x64")
    assert release_stem(descriptor=revised).endswith(f"{current}.2-windows-x64")
    assert release_stem().startswith(f"PixelScope-{current}-")
    assert manifest_path(descriptor=revised).name.startswith(f"PixelScopeSynthetic-{current}.2-")
    assert portable_zip_path(descriptor=revised).name.startswith(
        f"PixelScopeSynthetic-{current}.2-"
    )
    assert installer_path(descriptor=revised).name.startswith(f"PixelScopeSynthetic-{current}.2-")
    command = installer_command(Path("C:/ISCC.exe"), descriptor=revised)
    assert f"-dAppVersion={current}.2" in command
    assert f"-dAppFileVersion={current}.2" in command
    assert "-dAppVersionBuild=2" in command
    assert f"-dTargetReleaseStem={release_stem(descriptor=revised)}" in command
    assert 'StringStruct("FileVersion", "' + current + '.2")' in (
        render_windows_version_info(
            revised.effective_version,
            identity=(revised.app_dir, revised.executable, revised.display_name),
        )
    )
    v1 = windows_version_tuple(f"{current}.1")
    v2 = windows_version_tuple(f"{current}.2")
    assert v2 > v1
    assert windows_version_tuple(current)[3] == 0


def test_issue176_revision_manifest_records_provenance_and_refuses_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revised = load_target_descriptor(_descriptor_file(tmp_path, release_revision=7))
    root = tmp_path / "payload"
    root.mkdir()
    exe = root / revised.executable
    exe.write_bytes(b"payload-v1")
    output = tmp_path / "release.manifest.json"
    monkeypatch.setenv("PIXELSCOPE_PUBLIC_MAIN_SHA", "a" * 40)
    monkeypatch.setenv("PIXELSCOPE_DOWNSTREAM_SHA", "b" * 40)
    manifest = build_payload_manifest(root, descriptor=revised)
    assert manifest["version"] == revised.effective_version
    assert manifest["build_provenance"] == {
        "main_sha": "a" * 40,
        "downstream_sha": "b" * 40,
    }
    validate_payload_manifest(root, manifest, descriptor=revised)
    assert write_payload_manifest(root, destination=output, descriptor=revised) == output
    write_payload_manifest(root, destination=output, descriptor=revised)

    exe.write_bytes(b"payload-v2")
    with pytest.raises(DistributionValidationError, match="same downstream release identity"):
        write_payload_manifest(root, destination=output, descriptor=revised)
    assert json.loads(output.read_text()) == manifest
    monkeypatch.delenv("PIXELSCOPE_DOWNSTREAM_SHA")
    with pytest.raises(DistributionValidationError, match="PIXELSCOPE_DOWNSTREAM_SHA"):
        build_payload_manifest(root, descriptor=revised)


def test_issue176_inno_conversion_is_only_activated_by_non_smoke_downstream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = load_target_descriptor(
        _descriptor_file(
            tmp_path,
            release_revision=4,
            supersedes_installer_app_ids=["{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}"],
        )
    )
    monkeypatch.setattr("scripts.build_installer_release.sha256_file", lambda _path: "c" * 64)
    command = installer_command(Path("C:/ISCC.exe"), descriptor=target)
    assert "-dTargetCorePredecessor={6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}" in command
    assert "-dTargetManifestSha256=" + "c" * 64 in command
    assert "-dTargetExeSha256=" + "c" * 64 in command
    with pytest.raises(ValueError, match="non-smoke downstream AppId"):
        installer_command(Path("C:/ISCC.exe"), descriptor=target, app_id="unsafe-override")

    smoke_command = installer_command(
        Path("C:/ISCC.exe"),
        descriptor=target,
        smoke_build=True,
        app_id="PixelScope.P7B.Smoke",
    )
    assert "-dSmokeBuild=1" in smoke_command
    assert not any("-dTargetCorePredecessor=" in flag for flag in smoke_command)
    assert not any("-dTargetManifestSha256=" in flag for flag in smoke_command)
    assert not any("-dTargetExeSha256=" in flag for flag in smoke_command)
    assert not any(
        "-dTargetCorePredecessor=" in flag for flag in installer_command(Path("C:/ISCC.exe"))
    )


def test_issue176_shared_inno_has_fail_closed_conversion_lifecycle() -> None:
    inno = (
        Path(__file__).resolve().parents[2] / "packaging" / "installer" / "pixelscope.iss"
    ).read_text(encoding="utf-8")
    assert "#if defined(TargetCorePredecessor) && !defined(SmokeBuild)" in inno
    assert "function PrepareCoreConversion: Boolean;" in inno
    assert "WizardSilent then" in inno
    assert "ConversionSwitchPresent" in inno
    assert "MB_YESNO or MB_DEFBUTTON2, IDNO" in inno
    assert "function PrepareToInstall(var NeedsRestart: Boolean): String;" in inno
    assert "procedure CurStepChanged(CurStep: TSetupStep);" in inno
    assert "CurStep <> ssDone" in inno
    assert "VerifyDownstreamReadiness" in inno
    assert "GetSHA256OfFile" in inno
    assert "UninstallVerifiedCore" in inno
    assert "function GetCustomSetupExitCode: Integer;" in inno
    assert "PartialConversionExitCode = 77" in inno


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell integrity smoke")
def test_issue176_installed_payload_verifier_checks_all_manifest_members(
    tmp_path: Path,
) -> None:
    target = load_target_descriptor(_descriptor_file(tmp_path))
    root = tmp_path / target.app_dir
    root.mkdir()
    (root / target.executable).write_bytes(b"fake-exe")
    dll = root / "library.dll"
    dll.write_bytes(b"original-runtime")
    manifest = build_payload_manifest(root, descriptor=target)
    assert len(manifest["files"]) == 2
    manifest_file = root / "release-manifest.json"
    script = (
        Path(__file__).resolve().parents[2]
        / "packaging"
        / "installer"
        / "verify_downstream_payload.ps1"
    )
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-InstallRoot",
        str(root),
        "-ExpectedProduct",
        target.display_name,
        "-ExpectedVersion",
        target.effective_version,
        "-ExpectedExeName",
        target.executable,
    ]

    def check() -> int:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result.returncode

    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    assert check() == 0
    dll.write_bytes(b"tampered-runtime")
    assert check() != 0
    dll.unlink()
    assert check() != 0
    dll.write_bytes(b"original-runtime")
    manifest["files"][0]["path"] = "../escape.dll"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    assert check() != 0


def test_issue176_m3_conversion_never_trusts_manifest_hash_only() -> None:
    root = Path(__file__).resolve().parents[2]
    inno = (root / "packaging" / "installer" / "pixelscope.iss").read_text(encoding="utf-8")
    assert "function VerifyInstalledPayload: Boolean;" in inno
    assert "Result := VerifyInstalledPayload" in inno
    assert "GetSHA256OfFile" in inno
    assert "ConversionFailed := True" in inno
    assert "function GetCustomSetupExitCode: Integer;" in inno
    assert "UnsafeReparsePath(ChangeFileExt(ExpectedUninstaller, '.dat'))" in inno
    preflight = inno.split("function PrepareCoreConversion: Boolean;", 1)[1].split(
        "function PrepareToInstall", 1
    )[0]
    assert "RegKeyExists(HKLM32, CoreUninstallKey)" in preflight
    assert "RegKeyExists(HKCU32, CoreUninstallKey)" not in preflight
    script = (root / "packaging" / "installer" / "verify_downstream_payload.ps1").read_text(
        encoding="utf-8"
    )
    assert "Get-FileHash" in script and "ConvertFrom-Json" in script
    assert "ReparsePoint" in script


@pytest.mark.parametrize("produces_expected_target", [False, True])
def test_custom_build_cannot_reuse_stale_artifact_when_spec_builds_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, produces_expected_target: bool
) -> None:
    target = load_target_descriptor(_descriptor_file(tmp_path))
    monkeypatch.setattr("scripts.package_target_descriptor.REPO_ROOT", tmp_path)
    monkeypatch.setattr(release_builder, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(release_builder, "DIST_ROOT", tmp_path / "dist")
    monkeypatch.setattr(release_builder, "validate_release_host", lambda: None)
    monkeypatch.setattr(release_builder, "write_windows_version_info", lambda **_kw: None)
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("offline guide", encoding="utf-8")
    monkeypatch.setattr(release_builder, "build_user_guide", lambda **_kw: site)

    stale_root = target.output_root
    stale_root.mkdir(parents=True)
    (stale_root / target.executable).write_bytes(b"stale binary")
    public_root = tmp_path / "dist" / "PixelScope"
    public_root.mkdir()
    public_exe = public_root / "PixelScope.exe"
    public_exe.write_bytes(b"public binary")

    def fake_build(_command: list[str], **_kwargs: object) -> None:
        # Before the PyInstaller subprocess starts, stale custom artifacts
        # must be gone; unrelated Core output must remain untouched.
        assert not stale_root.exists()
        assert public_exe.read_bytes() == b"public binary"
        if produces_expected_target:
            stale_root.mkdir()
            (stale_root / target.executable).write_bytes(b"new binary")
        else:
            (public_root / "wrong-spec-built.txt").write_text("wrong COLLECT")

    monkeypatch.setattr(release_builder.subprocess, "run", fake_build)
    validated: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        release_builder,
        "validate_artifact",
        lambda root, *, executable_name: validated.append((root, executable_name)),
    )

    if not produces_expected_target:
        with pytest.raises(RuntimeError, match="did not produce the expected onedir"):
            release_builder.build_public_target(descriptor=target)
        assert not stale_root.exists()
        assert not validated
    else:
        assert release_builder.build_public_target(descriptor=target) == stale_root
        assert (stale_root / target.executable).read_bytes() == b"new binary"
        assert (stale_root / "help" / "index.html").read_text() == "offline guide"
        assert validated == [(stale_root, target.executable)]
    assert public_exe.read_bytes() == b"public binary"


def test_third_target_manifest_portable_zip_and_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = load_target_descriptor(_descriptor_file(tmp_path))
    monkeypatch.setattr("scripts.package_target_descriptor.REPO_ROOT", tmp_path)
    root = target.output_root
    # A tiny frozen-tree stand-in: no secret, Qt runtime, compiler or live server.
    root.mkdir(parents=True, exist_ok=True)
    (root / target.executable).write_bytes(b"synthetic exe")
    (root / "library.dll").write_bytes(b"synthetic runtime")
    release_root = tmp_path / "release"
    release_root.mkdir()
    version = "1.2.3"
    manifest = build_payload_manifest(root, version=version, descriptor=target)
    assert manifest["product"] == target.display_name
    assert manifest["payload_root"] == target.app_dir
    validate_payload_manifest(root, manifest, descriptor=target)

    # Synthetic package flow: the portable builder owns archiving and places
    # target-specific manifest/notices under the archive root.
    monkeypatch.setattr(portable, "RELEASE_ROOT", release_root)
    monkeypatch.setattr(portable, "validate_artifact", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        portable,
        "release_stem",
        lambda **_kw: release_stem(version, descriptor=target),
    )
    monkeypatch.setattr(
        portable,
        "portable_zip_path",
        lambda **_kw: release_root / portable_zip_path(version, descriptor=target).name,
    )

    def _write_manifest(_root: Path, **_kwargs: object) -> Path:
        file = release_root / manifest_path(version, descriptor=target).name
        file.write_text(json.dumps(manifest), encoding="utf-8")
        return file

    def _write_notices(**_kwargs: object) -> Path:
        file = release_root / notice_path(version, descriptor=target).name
        file.write_text("synthetic license inventory\n", encoding="utf-8")
        return file

    monkeypatch.setattr(portable, "write_payload_manifest", _write_manifest)
    monkeypatch.setattr(portable, "write_third_party_notices", _write_notices)
    archive = portable.build_portable_release(target)
    assert archive.is_file()
    with zipfile.ZipFile(archive) as zipped:
        prefix = release_stem(version, descriptor=target)
        files = set(zipped.namelist())
        assert f"{prefix}/{target.executable}" in files
        assert f"{prefix}/release-manifest.json" in files
        assert f"{prefix}/THIRD_PARTY_NOTICES.txt" in files

    # Complete the synthetic release artifact inventory and verify scoped
    # bundle validation does not confuse Core files with this new target.
    (release_root / installer_path(version, descriptor=target).name).write_bytes(b"setup")
    (release_root / "PixelScope-1.2.3-windows-x64-setup.exe").write_bytes(b"public setup")
    paths = validate_release_bundle(
        release_root=release_root,
        descriptor=target,
        version=version,
    )
    assert len(paths) == 4
    assert all(path.is_file() for path in paths)

    # Public/other-target release files may coexist, but the selected
    # custom stem must not have undeclared extra artifacts.
    extra = release_root / f"{release_stem(version, descriptor=target)}-debug.txt"
    extra.write_text("unexpected", encoding="utf-8")
    with pytest.raises(Exception, match="unexpected files"):
        validate_release_bundle(release_root=release_root, descriptor=target, version=version)
    extra.unlink()
    validate_release_bundle(release_root=release_root, descriptor=target, version=version)

    (root / "library.dll").write_bytes(b"tampered")
    with pytest.raises(Exception, match="size mismatch|SHA-256 mismatch"):
        validate_payload_manifest(root, manifest, descriptor=target)


def test_additional_requirements_extend_runtime_notice_license_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirements = tmp_path / "private-runtime.txt"
    requirements.write_text("internal-model-adapter==1.0\n", encoding="utf-8")
    fake_dist = SimpleNamespace(metadata={"Name": "internal-model-adapter"})
    monkeypatch.setattr(notices, "required_runtime_distributions", lambda: ())
    monkeypatch.setattr(notices, "_distribution_license_files", lambda _dist: ())
    monkeypatch.setattr(notices, "_license_metadata", lambda _dist: "MIT")
    notices._validate_runtime_inventory((fake_dist,), requirements)
    with pytest.raises(RuntimeError, match="missing runtime distributions"):
        notices._validate_runtime_inventory((), requirements)

    requirements.write_text("-r private-secrets.txt\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unsupported release notice requirement syntax"):
        notices._validate_runtime_inventory((fake_dist,), requirements)
