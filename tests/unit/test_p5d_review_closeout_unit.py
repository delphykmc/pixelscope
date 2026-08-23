from __future__ import annotations

import hashlib
import struct
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from pixelscope.io.image_reader import read_image
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_scene_inspection import (
    inspect_unavailable_reason,
    probe_image_dimensions,
)
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_v2_domain import ResultV2
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_reader import load_result_v2


def _load_result(tmp_path: Path) -> ResultV2:
    root = write_golden_result_v2(tmp_path / "result")
    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    return outcome.result


def test_ordinary_decoder_binds_pixels_to_exact_encoded_sha(tmp_path: Path) -> None:
    path = tmp_path / "source.png"
    image = np.arange(18 * 24 * 3, dtype=np.uint8).reshape(18, 24, 3)
    assert cv2.imwrite(str(path), image)

    encoded = path.read_bytes()
    document = read_image(path)

    assert document.encoded_source_sha256 == hashlib.sha256(encoded).hexdigest()
    assert document.shape[:2] == (18, 24)


def test_p5d_probe_reuses_p5c_bitmapcoreheader_support(tmp_path: Path) -> None:
    path = tmp_path / "core.bmp"
    width = 13
    height = 7
    file_header = b"BM" + struct.pack("<IHHI", 26, 0, 0, 26)
    core_header = struct.pack("<IHHHH", 12, width, height, 1, 24)
    path.write_bytes(file_header + core_header)

    assert probe_image_dimensions(path) == (width, height)


def test_p5d_probe_reuses_p5c_large_jpeg_metadata_budget(tmp_path: Path) -> None:
    path = tmp_path / "large-metadata.jpg"
    app_payload = b"\x00" * 65_533
    app_segment = b"\xff\xe0" + struct.pack(">H", 65_535) + app_payload
    metadata = app_segment * 17
    sof = b"\xff\xc0" + struct.pack(">H", 7) + bytes([8]) + struct.pack(">HH", 37, 53)
    path.write_bytes(b"\xff\xd8" + metadata + sof)

    assert path.stat().st_size > 1024 * 1024
    assert probe_image_dimensions(path) == (53, 37)


def test_same_source_id_may_bind_multiple_variants_for_native_inspect(tmp_path: Path) -> None:
    result = _load_result(tmp_path)
    scene = result.scenes[0]
    first = replace(scene.sources[0].source, storage_root_id="shared")
    bindings = (
        replace(scene.sources[0], source=first),
        replace(scene.sources[1], source=first),
    )
    result = replace(
        result,
        scenes=(replace(scene, sources=bindings), *result.scenes[1:]),
    )
    settings = RemoteIqaSettings(
        storage_roots=(RemoteIqaStorageRoot("shared", r"C:\iqa"),),
    )

    assert inspect_unavailable_reason(result, scene.scene_id, settings) is None


def test_distinct_source_ids_cannot_alias_one_native_locator(tmp_path: Path) -> None:
    result = _load_result(tmp_path)
    scene = result.scenes[0]
    first = replace(scene.sources[0].source, storage_root_id="shared")
    second = replace(
        scene.sources[1].source,
        storage_root_id="shared",
        relative_path=first.relative_path,
    )
    bindings = (
        replace(scene.sources[0], source=first),
        replace(scene.sources[1], source=second),
    )
    result = replace(
        result,
        scenes=(replace(scene, sources=bindings), *result.scenes[1:]),
    )
    settings = RemoteIqaSettings(
        storage_roots=(RemoteIqaStorageRoot("shared", r"C:\iqa"),),
    )

    assert inspect_unavailable_reason(result, scene.scene_id, settings) == (
        "Distinct source identities share one native source path"
    )
