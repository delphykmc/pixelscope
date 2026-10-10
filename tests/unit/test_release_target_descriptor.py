"""Issue #156 U2: synthetic third-target distribution end-to-end contract."""

from __future__ import annotations

import json
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
    build_payload_manifest,
    installer_path,
    manifest_path,
    notice_path,
    portable_zip_path,
    release_stem,
    validate_payload_manifest,
)
from scripts.package_target_descriptor import load_target_descriptor
from scripts.release_contract import render_windows_version_info
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
