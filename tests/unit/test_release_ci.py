from __future__ import annotations

from pathlib import Path

import pytest
from scripts.distribution_contract import (
    installer_path,
    manifest_path,
    notice_path,
    portable_zip_path,
    release_stem,
    write_payload_manifest,
)
from scripts.release_contract import REPO_ROOT
from scripts.validate_ci_release_bundle import (
    CiReleaseBundleError,
    validate_ci_release_bundle,
)


def _write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _valid_bundle(tmp_path: Path, *, version: str = "1.2.3") -> tuple[Path, Path]:
    app_dir = tmp_path / "dist" / "PixelScope"
    release_root = tmp_path / "release"
    _write(app_dir / "PixelScope.exe", b"exe")
    _write(app_dir / "nested" / "runtime.dll", b"runtime")

    write_payload_manifest(
        app_dir,
        destination=release_root / manifest_path(version).name,
        version=version,
    )
    _write(release_root / notice_path(version).name, b"notices")
    _write(release_root / portable_zip_path(version).name, b"zip")
    _write(release_root / installer_path(version).name, b"setup")
    return release_root, app_dir


def test_ci_release_bundle_accepts_exact_production_set(tmp_path: Path) -> None:
    release_root, app_dir = _valid_bundle(tmp_path)

    paths = validate_ci_release_bundle(
        release_root,
        app_dir,
        version="1.2.3",
    )

    assert {path.name for path in paths} == {
        manifest_path("1.2.3").name,
        notice_path("1.2.3").name,
        portable_zip_path("1.2.3").name,
        installer_path("1.2.3").name,
    }


def test_ci_release_bundle_rejects_missing_or_extra_files(tmp_path: Path) -> None:
    release_root, app_dir = _valid_bundle(tmp_path)
    installer = release_root / installer_path("1.2.3").name
    installer.unlink()

    with pytest.raises(CiReleaseBundleError, match="missing files"):
        validate_ci_release_bundle(release_root, app_dir, version="1.2.3")

    _write(installer, b"setup")
    _write(release_root / "unexpected.txt")
    with pytest.raises(CiReleaseBundleError, match="unexpected files"):
        validate_ci_release_bundle(release_root, app_dir, version="1.2.3")


def test_ci_release_bundle_rejects_disposable_smoke_setup(tmp_path: Path) -> None:
    release_root, app_dir = _valid_bundle(tmp_path)
    smoke_setup = release_root / f"{release_stem('1.2.3')}-smoke-setup.exe"
    _write(smoke_setup, b"smoke")

    with pytest.raises(CiReleaseBundleError, match="disposable smoke installer"):
        validate_ci_release_bundle(release_root, app_dir, version="1.2.3")


def test_ci_release_bundle_rejects_manifest_payload_drift(tmp_path: Path) -> None:
    release_root, app_dir = _valid_bundle(tmp_path)
    (app_dir / "nested" / "runtime.dll").write_bytes(b"tampered")

    with pytest.raises(RuntimeError, match="size mismatch|SHA-256 mismatch"):
        validate_ci_release_bundle(release_root, app_dir, version="1.2.3")


def test_windows_release_ci_pins_hosted_toolchain_and_actions() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "windows-release-ci.yml").read_text(
        encoding="utf-8"
    )

    assert "runs-on: windows-2022" in workflow
    assert 'PYTHON_VERSION: "3.10.11"' in workflow
    assert 'INNO_VERSION: "6.2.1"' in workflow
    assert (
        'INNO_SHA256: "50D21AAB83579245F88E2632A61B943AD47557E42B0F02E6CE2AFEF4CDD8DEB1"'
        in workflow
    )
    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" in workflow
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    assert "actions/cache@" not in workflow
    assert "pull_request_target:" not in workflow
    assert "permissions:\n  contents: read" in workflow


def test_windows_release_ci_runs_artifact_smokes_before_upload() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "windows-release-ci.yml").read_text(
        encoding="utf-8"
    )

    required_commands = (
        "scripts\\build_release.py",
        "scripts\\validate_release_artifact.py",
        "scripts\\smoke_packaged_release.py",
        "scripts\\build_portable_release.py",
        "scripts\\smoke_portable_release.py",
        "scripts\\build_installer_release.py",
        "scripts\\smoke_installer_release.py",
        "scripts\\validate_ci_release_bundle.py",
    )
    for command in required_commands:
        assert command in workflow

    assert "if-no-files-found: error" in workflow
    assert "retention-days: 14" in workflow
    assert "compression-level: 0" in workflow
    assert "workflow_dispatch:" in workflow
    assert "gh release" not in workflow.casefold()
    assert "softprops/action-gh-release" not in workflow.casefold()
