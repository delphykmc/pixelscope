from __future__ import annotations

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.distribution_contract import (  # noqa: E402
    MANIFEST_MEMBER_NAME,
    NOTICE_MEMBER_NAME,
    load_payload_manifest,
    portable_zip_path,
    release_stem,
    validate_payload_manifest,
)
from scripts.package_target_descriptor import (  # noqa: E402
    PackageTargetDescriptor,
    load_target_descriptor,
)
from scripts.release_contract import release_version  # noqa: E402
from scripts.smoke_packaged_release import smoke_executable  # noqa: E402
from scripts.validate_release_artifact import validate_artifact  # noqa: E402


def _validate_archive_members(archive: zipfile.ZipFile, expected_root: str) -> None:
    prefix = PurePosixPath(expected_root)
    for member in archive.infolist():
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"Portable ZIP contains an unsafe member: {member.filename!r}")
        if not path.parts or path.parts[0] != prefix.name:
            raise RuntimeError(
                "Portable ZIP member is outside the canonical archive root: " f"{member.filename!r}"
            )


def smoke_portable_release(
    archive_path: Path, *, descriptor: PackageTargetDescriptor | None = None
) -> None:
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)

    expected_root = release_stem(descriptor=descriptor) if descriptor else release_stem()
    with tempfile.TemporaryDirectory(prefix="pixelscope-portable-") as temp_dir:
        extraction_root = Path(temp_dir)
        with zipfile.ZipFile(archive_path, mode="r") as archive:
            _validate_archive_members(archive, expected_root)
            archive.extractall(extraction_root)

        app_root = extraction_root / expected_root
        manifest_path = app_root / MANIFEST_MEMBER_NAME
        notice_path = app_root / NOTICE_MEMBER_NAME
        if not manifest_path.is_file():
            raise RuntimeError("Portable ZIP is missing release-manifest.json")
        if not notice_path.is_file() or notice_path.stat().st_size == 0:
            raise RuntimeError("Portable ZIP is missing THIRD_PARTY_NOTICES.txt")

        manifest = load_payload_manifest(manifest_path)
        validate_payload_manifest(
            app_root,
            manifest,
            allow_distribution_metadata=True,
            expected_version=release_version(),
            descriptor=descriptor,
        )
        if descriptor is None:
            validate_artifact(app_root)
            smoke_executable(app_root / "PixelScope.exe")
        else:
            validate_artifact(app_root, executable_name=descriptor.executable)
            smoke_executable(
                app_root / descriptor.executable,
                title_fragment=descriptor.smoke_window_title,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify portable distribution")
    parser.add_argument("--target-descriptor", type=Path)
    args = parser.parse_args()
    descriptor = (
        load_target_descriptor(args.target_descriptor)
        if args.target_descriptor is not None
        else None
    )
    archive_path = portable_zip_path(descriptor=descriptor) if descriptor else portable_zip_path()
    smoke_portable_release(archive_path, descriptor=descriptor)
    print(f"Portable PixelScope smoke PASS: {archive_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
