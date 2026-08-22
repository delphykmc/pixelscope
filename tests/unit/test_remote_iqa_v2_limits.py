from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_reader import load_result_v2
from pixelscope.remote.iqa_v2_support import CorruptV2, load_npz


@pytest.fixture()
def golden_root(tmp_path: Path) -> Path:
    return write_golden_result_v2(tmp_path / "golden-v2")


def _manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    (root / "manifest.json").write_text(json.dumps(manifest, allow_nan=False), encoding="utf-8")


def test_manifest_size_ceiling_is_enforced(
    golden_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pixelscope.remote import iqa_v2_support as support

    monkeypatch.setattr(support, "V2_MANIFEST_LIMIT", 1)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.CORRUPT
    assert "manifest exceeds" in (outcome.reason or "")


@pytest.mark.parametrize(
    ("key", "limit_name"),
    [
        ("variants", "V2_MAX_VARIANTS"),
        ("attributes", "V2_MAX_ATTRIBUTES"),
        ("scenes", "V2_MAX_SCENES"),
    ],
)
def test_manifest_collection_ceilings_are_enforced(
    golden_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    limit_name: str,
) -> None:
    from pixelscope.remote import iqa_v2_manifest as manifest_module

    manifest = _manifest(golden_root)
    monkeypatch.setattr(manifest_module, limit_name, 1)
    _write_manifest(golden_root, manifest)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.INVALID
    assert "safety ceiling" in (outcome.reason or "")


def test_total_source_binding_ceiling_is_enforced(
    golden_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pixelscope.remote import iqa_v2_manifest as manifest_module

    monkeypatch.setattr(manifest_module, "V2_MAX_SOURCE_BINDINGS", 2)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.INVALID
    assert "source-binding safety ceiling" in (outcome.reason or "")


def test_grid_cell_ceiling_is_enforced(golden_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pixelscope.remote import iqa_v2_manifest as manifest_module

    monkeypatch.setattr(manifest_module, "V2_MAX_GRID_CELLS", 1)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.INVALID
    assert "cell safety ceiling" in (outcome.reason or "")


def test_detail_reference_count_ceiling_is_enforced(golden_root: Path) -> None:
    from pixelscope.remote.iqa_v2_support import V2_MAX_DETAIL_ARTIFACTS

    manifest = _manifest(golden_root)
    manifest["scenes"][0]["detail_artifacts"] = ["detail/opaque.bin"] * (
        V2_MAX_DETAIL_ARTIFACTS + 1
    )
    _write_manifest(golden_root, manifest)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.INVALID
    assert "detail_artifacts" in (outcome.reason or "")


def test_declared_summary_size_ceiling_is_enforced(golden_root: Path) -> None:
    from pixelscope.remote.iqa_v2_support import V2_SUMMARY_LIMIT

    manifest = _manifest(golden_root)
    manifest["summary_artifact"]["uncompressed_size"] = V2_SUMMARY_LIMIT + 1
    _write_manifest(golden_root, manifest)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.CORRUPT
    assert "summary_artifact" in (outcome.reason or "")


def test_declared_scene_size_ceiling_is_enforced(golden_root: Path) -> None:
    from pixelscope.remote.iqa_v2_support import V2_SCENE_LIMIT

    manifest = _manifest(golden_root)
    manifest["scenes"][0]["grid_artifact"]["uncompressed_size"] = V2_SCENE_LIMIT + 1
    _write_manifest(golden_root, manifest)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.CORRUPT
    assert "grid_artifact" in (outcome.reason or "")


def test_malformed_npz_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "malformed.npz"
    path.write_bytes(b"not-a-zip")
    with pytest.raises(CorruptV2, match="corrupt"):
        load_npz(
            path,
            total_limit=1024,
            expected={"x": (np.dtype("float64"), (1,))},
        )


def test_wrong_npz_shape_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "wrong-shape.npz"
    np.savez(path, x=np.asarray([1.0, 2.0], dtype=np.float64))
    with pytest.raises(CorruptV2, match="dtype/rank/shape mismatch"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("float64"), (1,))},
        )


def test_npz_on_disk_ceiling_is_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pixelscope.remote import iqa_v2_support as support

    path = tmp_path / "archive-limit.npz"
    np.savez(path, x=np.asarray([1.0], dtype=np.float64))
    monkeypatch.setattr(support, "V2_ARCHIVE_ON_DISK_LIMIT", 1)
    with pytest.raises(CorruptV2, match="on-disk safety ceiling"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("float64"), (1,))},
        )


def test_npz_member_size_ceiling_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pixelscope.remote import iqa_v2_support as support

    path = tmp_path / "member-limit.npz"
    np.savez(path, x=np.asarray([1.0], dtype=np.float64))
    monkeypatch.setattr(support, "V2_NPY_MEMBER_SIZE_LIMIT", 1)
    with pytest.raises(CorruptV2, match="member exceeds metadata safety ceiling"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("float64"), (1,))},
        )
