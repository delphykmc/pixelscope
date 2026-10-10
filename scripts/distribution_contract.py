from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Final

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.package_target_descriptor import PackageTargetDescriptor  # noqa: E402
from scripts.release_contract import APP_DIR, REPO_ROOT, release_version  # noqa: E402

TARGET_ID: Final = "windows-x64"
RELEASE_ROOT: Final = REPO_ROOT / "release"
MANIFEST_MEMBER_NAME: Final = "release-manifest.json"
NOTICE_MEMBER_NAME: Final = "THIRD_PARTY_NOTICES.txt"
MANIFEST_SCHEMA_VERSION: Final = 1
_DISTRIBUTION_METADATA_NAMES: Final = frozenset({MANIFEST_MEMBER_NAME, NOTICE_MEMBER_NAME})
_HEX_DIGITS: Final = frozenset("0123456789abcdefABCDEF")


class DistributionValidationError(RuntimeError):
    """Raised when a distribution no longer matches the canonical onedir payload."""


def release_stem(
    version: str | None = None, *, descriptor: PackageTargetDescriptor | None = None
) -> str:
    value = (version or release_version()).strip()
    if not value or any(char in value for char in '<>:"/\\|?*'):
        raise ValueError(f"Release version is not safe for artifact names: {value!r}")
    prefix = descriptor.stem_prefix if descriptor is not None else "PixelScope"
    return f"{prefix}-{value}-{TARGET_ID}"


def manifest_path(
    version: str | None = None, *, descriptor: PackageTargetDescriptor | None = None
) -> Path:
    return RELEASE_ROOT / f"{release_stem(version, descriptor=descriptor)}.manifest.json"


def notice_path(
    version: str | None = None, *, descriptor: PackageTargetDescriptor | None = None
) -> Path:
    return RELEASE_ROOT / f"{release_stem(version, descriptor=descriptor)}-THIRD_PARTY_NOTICES.txt"


def portable_zip_path(
    version: str | None = None, *, descriptor: PackageTargetDescriptor | None = None
) -> Path:
    return RELEASE_ROOT / f"{release_stem(version, descriptor=descriptor)}-portable.zip"


def installer_path(
    version: str | None = None, *, descriptor: PackageTargetDescriptor | None = None
) -> Path:
    return RELEASE_ROOT / f"{release_stem(version, descriptor=descriptor)}-setup.exe"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a release/distribution file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_files(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )


def build_payload_manifest(
    root: Path = APP_DIR,
    *,
    version: str | None = None,
    descriptor: PackageTargetDescriptor | None = None,
) -> dict[str, object]:
    root = root.resolve()
    files = [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in _payload_files(root)
    ]
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "product": descriptor.display_name if descriptor is not None else "PixelScope",
        "version": version or release_version(),
        "target": TARGET_ID,
        "payload_root": descriptor.app_dir if descriptor is not None else "PixelScope",
        "files": files,
    }


def write_payload_manifest(
    root: Path = APP_DIR,
    destination: Path | None = None,
    *,
    version: str | None = None,
    descriptor: PackageTargetDescriptor | None = None,
) -> Path:
    output = (destination or manifest_path(version, descriptor=descriptor)).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_payload_manifest(root, version=version, descriptor=descriptor)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def load_payload_manifest(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DistributionValidationError("release manifest root must be an object")
    return data


def validate_payload_manifest(
    root: Path,
    manifest: dict[str, object],
    *,
    allow_distribution_metadata: bool = False,
    allowed_extra_names: frozenset[str] = frozenset(),
    expected_version: str | None = None,
    descriptor: PackageTargetDescriptor | None = None,
) -> None:
    root = root.resolve()
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise DistributionValidationError("unsupported release manifest schema")
    expected_product = descriptor.display_name if descriptor is not None else "PixelScope"
    if manifest.get("product") != expected_product:
        raise DistributionValidationError("release manifest product mismatch")
    if manifest.get("target") != TARGET_ID:
        raise DistributionValidationError("release manifest target mismatch")
    expected_root = descriptor.app_dir if descriptor is not None else "PixelScope"
    if manifest.get("payload_root") != expected_root:
        raise DistributionValidationError("release manifest payload root mismatch")

    manifest_version = manifest.get("version")
    if not isinstance(manifest_version, str) or not manifest_version.strip():
        raise DistributionValidationError("release manifest version is invalid")
    if expected_version is not None and manifest_version != expected_version:
        raise DistributionValidationError(
            f"release manifest version mismatch: {manifest_version!r} != {expected_version!r}"
        )

    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise DistributionValidationError("release manifest contains no payload files")

    expected: dict[str, tuple[int, str]] = {}
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict):
            raise DistributionValidationError("release manifest file entry must be an object")
        relative = raw_entry.get("path")
        size = raw_entry.get("size")
        digest = raw_entry.get("sha256")
        if not isinstance(relative, str) or not relative:
            raise DistributionValidationError("release manifest file path is invalid")
        pure_path = PurePosixPath(relative)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            raise DistributionValidationError(f"unsafe manifest path: {relative!r}")
        if not isinstance(size, int) or size < 0:
            raise DistributionValidationError(f"invalid manifest size for {relative!r}")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in _HEX_DIGITS for char in digest)
        ):
            raise DistributionValidationError(f"invalid SHA-256 for {relative!r}")
        if relative in expected:
            raise DistributionValidationError(f"duplicate manifest path: {relative!r}")
        expected[relative] = (size, digest.casefold())

    actual_files = _payload_files(root)
    actual_relative = {path.relative_to(root).as_posix() for path in actual_files}
    if allow_distribution_metadata:
        actual_relative.difference_update(_DISTRIBUTION_METADATA_NAMES)
    actual_relative.difference_update(allowed_extra_names)

    expected_relative = set(expected)
    missing = sorted(expected_relative - actual_relative)
    extra = sorted(actual_relative - expected_relative)
    if missing:
        raise DistributionValidationError(f"manifest payload files are missing: {missing}")
    if extra:
        raise DistributionValidationError(f"manifest contains unexpected payload files: {extra}")

    for relative, (expected_size, expected_digest) in expected.items():
        path = root / Path(*PurePosixPath(relative).parts)
        if path.stat().st_size != expected_size:
            raise DistributionValidationError(f"payload size mismatch: {relative}")
        if sha256_file(path).casefold() != expected_digest:
            raise DistributionValidationError(f"payload SHA-256 mismatch: {relative}")
