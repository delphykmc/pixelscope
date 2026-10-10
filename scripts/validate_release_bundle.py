from __future__ import annotations

import argparse
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
from scripts.package_target_descriptor import (  # noqa: E402
    PackageTargetDescriptor,
    load_target_descriptor,
)
from scripts.release_contract import APP_DIR, release_version  # noqa: E402


class ReleaseBundleError(RuntimeError):
    """Raised when a production release bundle is incomplete or contaminated."""


def _expected_paths(
    release_root: Path, version: str, *, descriptor: PackageTargetDescriptor | None = None
) -> tuple[Path, ...]:
    return (
        release_root / manifest_path(version, descriptor=descriptor).name,
        release_root / notice_path(version, descriptor=descriptor).name,
        release_root / portable_zip_path(version, descriptor=descriptor).name,
        release_root / installer_path(version, descriptor=descriptor).name,
    )


def validate_release_bundle(
    release_root: Path = RELEASE_ROOT,
    app_dir: Path = APP_DIR,
    *,
    version: str | None = None,
    descriptor: PackageTargetDescriptor | None = None,
) -> tuple[Path, ...]:
    release_root = release_root.resolve()
    app_dir = (descriptor.output_root if descriptor is not None else app_dir).resolve()
    expected_version = version or release_version()

    if not release_root.is_dir():
        raise ReleaseBundleError(f"release directory does not exist: {release_root}")

    stem = release_stem(expected_version, descriptor=descriptor)
    smoke_setup = release_root / f"{stem}-smoke-setup.exe"
    if smoke_setup.exists():
        raise ReleaseBundleError(
            f"disposable smoke installer must not be retained: {smoke_setup.name}"
        )

    expected_paths = _expected_paths(release_root, expected_version, descriptor=descriptor)
    expected_names = {path.name for path in expected_paths}
    actual_names = {path.name for path in release_root.iterdir() if path.is_file()}

    missing = sorted(expected_names - actual_names)
    # Legacy public validation stays strict. In a shared custom release
    # workspace, accept other targets, but never ignore an unexpected
    # sidecar/artifact belonging to THIS versioned custom product.
    if descriptor is None:
        extra = sorted(actual_names - expected_names)
    else:
        owned_names = {
            name
            for name in actual_names
            if name.startswith((f"{stem}-", f"{stem}."))
        }
        extra = sorted(owned_names - expected_names)
    if missing:
        raise ReleaseBundleError(f"release bundle is missing files: {missing}")
    if extra:
        raise ReleaseBundleError(f"release bundle contains unexpected files: {extra}")

    for path in expected_paths:
        if path.stat().st_size <= 0:
            raise ReleaseBundleError(f"release artifact is empty: {path.name}")

    manifest = load_payload_manifest(
        release_root / manifest_path(expected_version, descriptor=descriptor).name
    )
    validate_payload_manifest(
        app_dir,
        manifest,
        expected_version=expected_version,
        descriptor=descriptor,
    )

    return expected_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release payload bundle")
    parser.add_argument("--target-descriptor", type=Path)
    args = parser.parse_args()
    descriptor = (
        load_target_descriptor(args.target_descriptor)
        if args.target_descriptor is not None
        else None
    )
    paths = validate_release_bundle(descriptor=descriptor)
    print("PixelScope production release bundle PASS")
    for path in paths:
        print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
