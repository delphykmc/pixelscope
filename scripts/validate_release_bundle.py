from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.distribution_contract import (  # noqa: E402
    RELEASE_ROOT,
    installer_path,
    load_payload_manifest,
    manifest_path,
    notice_path,
    portable_zip_path,
    release_stem,
    validate_payload_manifest,
)
from scripts.release_contract import APP_DIR, release_version  # noqa: E402


class ReleaseBundleError(RuntimeError):
    """Raised when a production release bundle is incomplete or contaminated."""


def _expected_paths(release_root: Path, version: str) -> tuple[Path, ...]:
    return (
        release_root / manifest_path(version).name,
        release_root / notice_path(version).name,
        release_root / portable_zip_path(version).name,
        release_root / installer_path(version).name,
    )


def validate_release_bundle(
    release_root: Path = RELEASE_ROOT,
    app_dir: Path = APP_DIR,
    *,
    version: str | None = None,
) -> tuple[Path, ...]:
    release_root = release_root.resolve()
    app_dir = app_dir.resolve()
    expected_version = version or release_version()

    if not release_root.is_dir():
        raise ReleaseBundleError(f"release directory does not exist: {release_root}")

    smoke_setup = release_root / f"{release_stem(expected_version)}-smoke-setup.exe"
    if smoke_setup.exists():
        raise ReleaseBundleError(
            f"disposable smoke installer must not be retained: {smoke_setup.name}"
        )

    expected_paths = _expected_paths(release_root, expected_version)
    expected_names = {path.name for path in expected_paths}
    actual_names = {path.name for path in release_root.iterdir() if path.is_file()}

    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing:
        raise ReleaseBundleError(f"release bundle is missing files: {missing}")
    if extra:
        raise ReleaseBundleError(f"release bundle contains unexpected files: {extra}")

    for path in expected_paths:
        if path.stat().st_size <= 0:
            raise ReleaseBundleError(f"release artifact is empty: {path.name}")

    manifest = load_payload_manifest(release_root / manifest_path(expected_version).name)
    validate_payload_manifest(
        app_dir,
        manifest,
        expected_version=expected_version,
    )

    return expected_paths


def main() -> int:
    paths = validate_release_bundle()
    print("PixelScope production release bundle PASS")
    for path in paths:
        print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
