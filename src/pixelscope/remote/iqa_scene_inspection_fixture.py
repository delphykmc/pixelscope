"""Deterministic P5-D fixture with real native sources and published logical locators."""

from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_storage import sha256_file
from pixelscope.remote.iqa_v2_domain import ResultV2, build_measurement_context_id
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_reader import load_result_v2

P5D_STORAGE_ROOT_ID = "p5d-fixture-root"
P5dFixtureScenario = Literal[
    "valid",
    "missing_source",
    "hash_mismatch",
    "dimension_mismatch",
    "missing_grid",
    "corrupt_grid",
]


@dataclass(frozen=True)
class P5dInspectionFixture:
    """Paths and logical-root metadata for one deterministic native Inspect fixture."""

    result_root: Path
    storage_root: Path
    storage_root_id: str
    source_paths: tuple[Path, ...]
    scene_ids: tuple[str, ...]


def write_p5d_inspection_fixture(
    root: Path,
    *,
    scenario: P5dFixtureScenario = "valid",
    storage_root_id: str = P5D_STORAGE_ROOT_ID,
    scene_count: int = 3,
) -> P5dInspectionFixture:
    """Write a published v2 result plus real PNG sources for native Scene inspection tests.

    The underlying schema-v2 golden writer retains its non-integer affine transform,
    non-zero valid/grid origins, discarded borders, multiple attributes, and invalid
    cells. This extension only replaces synthetic source hashes with hashes of actual
    deterministic native PNG files and publishes the additive logical root locator.
    """

    if scenario not in {
        "valid",
        "missing_source",
        "hash_mismatch",
        "dimension_mismatch",
        "missing_grid",
        "corrupt_grid",
    }:
        raise ValueError(f"unsupported P5-D fixture scenario: {scenario}")
    result_root = root / "result"
    storage_root = root / "storage"
    write_golden_result_v2(result_root, scene_count=scene_count)
    original_outcome = load_result_v2(result_root)
    if original_outcome.status is not LoadStatus.SUCCESS or not isinstance(
        original_outcome.result, ResultV2
    ):
        raise RuntimeError(original_outcome.reason or "unable to load base P5-D fixture")
    original = original_outcome.result

    manifest_path = result_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_paths: list[Path] = []
    context_ids: list[str] = []

    for scene_index, scene in enumerate(original.scenes):
        manifest_scene = manifest["scenes"][scene_index]
        updated_measurements = []
        for variant_index, measurement in enumerate(scene.sources):
            source = measurement.source
            local_path = storage_root.joinpath(*Path(source.relative_path).parts)
            _write_png(
                local_path,
                source.width,
                source.height,
                seed=scene_index * 17 + variant_index * 53 + 11,
            )
            source_paths.append(local_path)
            digest = sha256_file(local_path)
            updated_source = replace(
                source,
                sha256=digest,
                storage_root_id=storage_root_id,
            )
            updated_measurements.append(replace(measurement, source=updated_source))
            manifest_source = manifest_scene["sources"][variant_index]
            manifest_source["sha256"] = digest
            manifest_source["storage_root_id"] = storage_root_id

        context_id = build_measurement_context_id(
            scene.scene_id,
            updated_measurements,
            original.attributes,
            scene.context_provenance,
        )
        context_ids.append(context_id)
        manifest_scene["measurement_context_id"] = context_id
        _rewrite_npz_string(
            result_root / scene.grid_artifact,
            "measurement_context_id",
            np.asarray([context_id], dtype="<U68"),
        )

    _rewrite_npz_string(
        result_root / original.summary_artifact,
        "measurement_context_ids",
        np.asarray(context_ids, dtype="<U68"),
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    fixture = P5dInspectionFixture(
        result_root=result_root,
        storage_root=storage_root,
        storage_root_id=storage_root_id,
        source_paths=tuple(source_paths),
        scene_ids=tuple(scene.scene_id for scene in original.scenes),
    )
    _apply_scenario(fixture, scenario)
    return fixture


def _rewrite_npz_string(path: Path, key: str, value: np.ndarray[Any, Any]) -> None:
    with np.load(path, allow_pickle=False) as loaded:
        arrays = {name: loaded[name] for name in loaded.files}
    arrays[key] = value
    np.savez(path, **arrays)


def _apply_scenario(fixture: P5dInspectionFixture, scenario: P5dFixtureScenario) -> None:
    if scenario == "valid":
        return
    first_source = fixture.source_paths[0]
    if scenario == "missing_source":
        first_source.unlink()
        return
    if scenario == "hash_mismatch":
        _write_png(first_source, 1000, 700, seed=251)
        return
    if scenario == "dimension_mismatch":
        _write_png(first_source, 999, 700, seed=17)
        return
    first_grid = fixture.result_root / "scenes" / f"{fixture.scene_ids[0]}.npz"
    if scenario == "missing_grid":
        first_grid.unlink()
        return
    if scenario == "corrupt_grid":
        first_grid.write_bytes(b"not-a-valid-npz")
        return
    raise AssertionError(f"unhandled fixture scenario: {scenario}")


def _write_png(path: Path, width: int, height: int, *, seed: int) -> None:
    """Write a small-compressed, standards-compliant deterministic RGB PNG."""

    if width <= 0 or height <= 0:
        raise ValueError("PNG fixture dimensions must be positive")
    path.parent.mkdir(parents=True, exist_ok=True)
    red = seed & 0xFF
    green = (seed * 3 + 19) & 0xFF
    blue = (seed * 7 + 41) & 0xFF
    row = b"\x00" + bytes((red, green, blue)) * width
    raw = row * height
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        signature
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )
