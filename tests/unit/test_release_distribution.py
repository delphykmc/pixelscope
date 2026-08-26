from __future__ import annotations

import os
import runpy
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import build_installer_release as installer_module
from scripts import build_portable_release as portable_module
from scripts.build_installer_release import inno_major_version, installer_command
from scripts.build_third_party_notices import required_runtime_distributions
from scripts.distribution_contract import (
    DistributionValidationError,
    build_payload_manifest,
    installer_path,
    manifest_path,
    notice_path,
    portable_zip_path,
    release_stem,
    validate_payload_manifest,
)
from scripts.release_contract import REPO_ROOT


def _write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_distribution_names_derive_from_release_version() -> None:
    assert release_stem("1.2.3") == "PixelScope-1.2.3-windows-x64"
    assert manifest_path("1.2.3").name == "PixelScope-1.2.3-windows-x64.manifest.json"
    assert notice_path("1.2.3").name.endswith("-THIRD_PARTY_NOTICES.txt")
    assert portable_zip_path("1.2.3").name.endswith("-portable.zip")
    assert installer_path("1.2.3").name.endswith("-setup.exe")

    with pytest.raises(ValueError, match="safe for artifact names"):
        release_stem("1.2/3")


def test_payload_manifest_detects_tamper_and_unexpected_files(tmp_path: Path) -> None:
    root = tmp_path / "PixelScope"
    _write(root / "PixelScope.exe", b"exe")
    _write(root / "nested" / "runtime.dll", b"runtime")
    manifest = build_payload_manifest(root, version="1.2.3")

    validate_payload_manifest(root, manifest)

    (root / "nested" / "runtime.dll").write_bytes(b"tampered")
    with pytest.raises(DistributionValidationError, match="size mismatch|SHA-256 mismatch"):
        validate_payload_manifest(root, manifest)

    (root / "nested" / "runtime.dll").write_bytes(b"runtime")
    _write(root / "release-manifest.json")
    _write(root / "THIRD_PARTY_NOTICES.txt")
    validate_payload_manifest(root, manifest, allow_distribution_metadata=True)

    _write(root / "unins000.exe")
    with pytest.raises(DistributionValidationError, match="unexpected payload files"):
        validate_payload_manifest(root, manifest, allow_distribution_metadata=True)
    validate_payload_manifest(
        root,
        manifest,
        allow_distribution_metadata=True,
        allowed_extra_names=frozenset({"unins000.exe"}),
    )


def test_portable_zip_is_deterministic_for_identical_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = tmp_path / "payload"
    _write(payload / "PixelScope.exe", b"exe")
    nested = _write(payload / "nested" / "runtime.dll", b"runtime")
    release_root = tmp_path / "release"
    output = release_root / "PixelScope-1.2.3-windows-x64-portable.zip"

    def write_manifest(_root: Path) -> Path:
        path = release_root / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    def write_notices() -> Path:
        path = release_root / "notices.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("notices\n", encoding="utf-8")
        return path

    monkeypatch.setattr(portable_module, "APP_DIR", payload)
    monkeypatch.setattr(portable_module, "RELEASE_ROOT", release_root)
    monkeypatch.setattr(portable_module, "portable_zip_path", lambda: output)
    monkeypatch.setattr(
        portable_module,
        "release_stem",
        lambda: "PixelScope-1.2.3-windows-x64",
    )
    monkeypatch.setattr(portable_module, "write_payload_manifest", write_manifest)
    monkeypatch.setattr(portable_module, "write_third_party_notices", write_notices)
    monkeypatch.setattr(portable_module, "validate_artifact", lambda _root: None)

    first = portable_module.build_portable_release().read_bytes()
    os.utime(nested, (nested.stat().st_atime + 100, nested.stat().st_mtime + 100))
    second = portable_module.build_portable_release().read_bytes()

    assert first == second
    with zipfile.ZipFile(output) as archive:
        timestamps = {member.date_time for member in archive.infolist()}
    assert timestamps == {(1980, 1, 1, 0, 0, 0)}


def test_inno_script_preserves_per_user_no_admin_contract() -> None:
    script = (REPO_ROOT / "packaging" / "installer" / "pixelscope.iss").read_text(
        encoding="utf-8"
    )

    assert "PrivilegesRequired=lowest" in script
    assert r"DefaultDirName={localappdata}\Programs\PixelScope" in script
    assert "ArchitecturesAllowed=x64" in script
    assert "ArchitecturesInstallIn64BitMode=x64" in script
    assert "AppId={{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}" in script
    assert "[Registry]" not in script
    assert "deletekey" not in script.casefold()
    assert "SignTool=" not in script
    assert "[Run]" not in script


def test_installer_command_uses_same_payload_and_versioned_outputs() -> None:
    command = installer_command(Path("C:/Inno Setup 6/ISCC.exe"))
    joined = "\n".join(command)

    assert command[1] == "/Qp"
    assert str(installer_module.APP_DIR.resolve()) in joined
    assert str(installer_module.manifest_path().resolve()) in joined
    assert str(installer_module.notice_path().resolve()) in joined
    assert installer_module.installer_path().stem in joined
    assert str(installer_module.INNO_SCRIPT.resolve()) == command[-1]


def test_inno_major_version_parses_compiler_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        installer_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="Inno Setup 6 Command-Line Compiler\n",
            stderr="",
            returncode=0,
        ),
    )

    assert inno_major_version(Path("ISCC.exe")) == 6


def test_runtime_notice_inventory_tracks_pinned_runtime_requirements() -> None:
    names = {name.casefold() for name in required_runtime_distributions()}

    assert "numpy" in names
    assert "opencv-python" in names
    assert "pyside6" in names
    assert "httpx" in names
    assert "shiboken6" in names


def test_distribution_scripts_support_repo_root_file_execution_imports() -> None:
    for script_name in (
        "build_third_party_notices.py",
        "build_portable_release.py",
        "smoke_portable_release.py",
        "build_installer_release.py",
        "smoke_installer_release.py",
    ):
        namespace = runpy.run_path(str(REPO_ROOT / "scripts" / script_name))
        assert "main" in namespace
