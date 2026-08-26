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
