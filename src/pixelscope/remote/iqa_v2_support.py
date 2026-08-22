"""Bounded artifact and parsing support shared by the schema-v2 IQA reader."""

from __future__ import annotations

import json
import math
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import numpy as np
from numpy.lib import format as npy_format

V2_MANIFEST_LIMIT = 8 * 1024 * 1024
V2_SUMMARY_LIMIT = 128 * 1024 * 1024
V2_SCENE_LIMIT = 128 * 1024 * 1024
V2_ARRAY_LIMIT = 32 * 1024 * 1024
V2_NPY_MEMBER_SIZE_LIMIT = V2_ARRAY_LIMIT + 64 * 1024
V2_ARCHIVE_ON_DISK_LIMIT = 130 * 1024 * 1024
V2_NPZ_MEMBER_LIMIT = 192
V2_MAX_VARIANTS = 32
V2_MAX_SCENES = 512
V2_MAX_ATTRIBUTES = 32
V2_MAX_SOURCE_BINDINGS = 1024
V2_MAX_GRID_CELLS = 65_536
V2_MAX_DETAIL_ARTIFACTS = 64
V2_MAX_ID_LENGTH = 128
V2_MAX_LABEL_LENGTH = 256
V2_MAX_PROVENANCE_LENGTH = 512
V2_MAX_SOURCE_PATH_LENGTH = 2048
V2_MAX_ARTIFACT_PATH_LENGTH = 1024


class InvalidV2(ValueError):
    pass


class CorruptV2(ValueError):
    pass


class UnsupportedV2(ValueError):
    pass


def read_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    if not path.is_file():
        raise CorruptV2("missing manifest.json publication marker")
    try:
        if path.stat().st_size > V2_MANIFEST_LIMIT:
            raise CorruptV2("manifest exceeds 8 MiB schema-v2 safety ceiling")
        value = json.loads(path.read_text(encoding="utf-8"))
    except CorruptV2:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorruptV2(f"manifest is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise InvalidV2("manifest must be a JSON object")
    return value


def validate_artifact_reference(reference: str) -> Path:
    """Validate path syntax without touching the filesystem.

    This is the ordinary-open boundary for deferred Scene/detail artifacts. Both
    POSIX and Windows traversal/absolute semantics are rejected independent of the
    host OS; existence and containment are checked only when an artifact is opened.
    """
    if "\x00" in reference:
        raise CorruptV2("artifact path contains NUL")
    posix = PurePosixPath(reference)
    windows = PureWindowsPath(reference)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise CorruptV2("artifact path must be a relative path beneath result root")
    if not posix.parts or str(posix) in {"", "."}:
        raise CorruptV2("artifact path must name a file beneath result root")
    return Path(*posix.parts)


def safe_artifact(root: Path, reference: str) -> Path:
    path = validate_artifact_reference(reference)
    try:
        resolved_root = root.resolve(strict=True)
        resolved = (root / path).resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise CorruptV2(f"artifact is missing or escapes result root: {reference}") from exc
    if not resolved.is_file():
        raise CorruptV2(f"artifact is not a regular file: {reference}")
    return resolved


def load_npz(
    path: Path,
    *,
    total_limit: int,
    expected: dict[str, tuple[np.dtype[Any], tuple[int, ...]]],
    declared_size: int | None = None,
) -> dict[str, np.ndarray[Any, Any]]:
    try:
        if path.stat().st_size > V2_ARCHIVE_ON_DISK_LIMIT:
            raise CorruptV2(f"artifact {path.name} exceeds on-disk safety ceiling")
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > V2_NPZ_MEMBER_LIMIT:
                raise CorruptV2(f"artifact {path.name} has too many members")
            filenames = [info.filename for info in infos]
            if len(filenames) != len(set(filenames)):
                raise CorruptV2(f"artifact {path.name} has duplicate members")
            actual_total = sum(info.file_size for info in infos)
            if actual_total > total_limit:
                raise CorruptV2(f"artifact {path.name} exceeds uncompressed safety ceiling")
            if declared_size is not None and actual_total != declared_size:
                raise CorruptV2(f"artifact {path.name} declared/actual size mismatch")
            for info in infos:
                if info.flag_bits & 0x1:
                    raise CorruptV2(f"artifact {path.name} has encrypted members")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise CorruptV2(f"artifact {path.name} uses unsupported member compression")
                if (
                    info.file_size > V2_NPY_MEMBER_SIZE_LIMIT
                    or info.compress_size > V2_ARCHIVE_ON_DISK_LIMIT
                ):
                    raise CorruptV2(f"artifact {path.name} member exceeds metadata safety ceiling")
            names = set(filenames)
            expected_names = {f"{key}.npy" for key in expected}
            if names != expected_names:
                raise CorruptV2(f"artifact {path.name} has unexpected array members")
            for key, (expected_dtype, expected_shape) in expected.items():
                info = archive.getinfo(f"{key}.npy")
                with archive.open(info) as stream:
                    version = npy_format.read_magic(stream)  # type: ignore[no-untyped-call]
                    header_reader: Callable[..., tuple[tuple[int, ...], bool, np.dtype[Any]]]
                    if version == (1, 0):
                        header_reader = npy_format.read_array_header_1_0
                    elif version in {(2, 0), (3, 0)}:
                        header_reader = npy_format.read_array_header_2_0
                    else:
                        raise CorruptV2(f"unsupported NPY version {version}")
                    shape, _fortran, dtype = header_reader(  # type: ignore[no-untyped-call]
                        stream
                    )
                if dtype.hasobject:
                    raise CorruptV2(f"object/pickle array rejected: {key}")
                if dtype != expected_dtype or shape != expected_shape:
                    raise CorruptV2(f"array {key} dtype/rank/shape mismatch: {dtype} {shape}")
                if int(dtype.itemsize * math.prod(shape)) > V2_ARRAY_LIMIT:
                    raise CorruptV2(f"array {key} exceeds safety ceiling")
        with np.load(path, allow_pickle=False) as loaded:
            return {key: np.asarray(loaded[key]) for key in expected}
    except CorruptV2:
        raise
    except (
        OSError,
        ValueError,
        RuntimeError,
        NotImplementedError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        EOFError,
    ) as exc:
        raise CorruptV2(f"artifact {path.name} is corrupt: {exc}") from exc
