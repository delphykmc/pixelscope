from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_partial import PartialResultV2
from pixelscope.remote.iqa_v2_reader import load_result_v2


def _manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def _partial_root(tmp_path: Path, failed_status: str) -> Path:
    root = write_golden_result_v2(tmp_path / f"partial-{failed_status}", scene_count=4)
    manifest = _manifest(root)
    manifest["publication_state"] = "partial"
    manifest["scene_outcomes"] = [
        {"scene_id": scene["scene_id"], "status": "succeeded"}
        for scene in manifest["scenes"]
    ] + [
        {
            "scene_id": "scene_000004",
            "status": failed_status,
            "error": {
                "code": "future.server.code/v7",
                "message": "bounded diagnostic for the unavailable Scene",
                "retryable": failed_status == "failed",
            },
        }
    ]
    _write_manifest(root, manifest)
    return root


def test_complete_v2_golden_remains_complete_and_unchanged(tmp_path: Path) -> None:
    root = write_golden_result_v2(tmp_path / "complete", scene_count=4)

    direct = load_result_v2(root)
    canonical = load_result(root)

    assert direct.status is LoadStatus.SUCCESS
    assert canonical.status is LoadStatus.SUCCESS
    assert not isinstance(direct.result, PartialResultV2)
    assert not isinstance(canonical.result, PartialResultV2)


@pytest.mark.parametrize("failed_status", ("failed", "cancelled"))
def test_partial_v2_golden_opens_successful_scenes_and_preserves_diagnostics(
    tmp_path: Path,
    failed_status: str,
) -> None:
    root = _partial_root(tmp_path, failed_status)

    direct = load_result_v2(root)
    canonical = load_result(root)

    assert direct.status is LoadStatus.SUCCESS, direct.reason
    assert canonical.status is LoadStatus.SUCCESS, canonical.reason
    assert isinstance(direct.result, PartialResultV2)
    result = direct.result
    assert result.publication_state == "partial"
    assert result.successful_scene_count == 4
    assert result.requested_scene_count == 5
    assert [item.scene_id for item in result.scenes] == [
        "scene_000000",
        "scene_000001",
        "scene_000002",
        "scene_000003",
    ]
    failed = result.unsuccessful_scene_outcomes
    assert len(failed) == 1
    assert failed[0].scene_id == "scene_000004"
    assert failed[0].status == failed_status
    assert failed[0].error_code == "future.server.code/v7"
    assert failed[0].error_message == "bounded diagnostic for the unavailable Scene"

    model = IqaExplorerModel(result)
    assert model.scene_ids == (
        "scene_000000",
        "scene_000001",
        "scene_000002",
        "scene_000003",
    )
    with pytest.raises(StopIteration):
        result.scene("scene_000004")


def test_partial_zero_success_is_invalid_before_numerical_scene_parsing(tmp_path: Path) -> None:
    root = write_golden_result_v2(tmp_path / "zero-success", scene_count=2)
    manifest = _manifest(root)
    manifest["publication_state"] = "partial"
    manifest["scene_outcomes"] = [
        {
            "scene_id": "scene_000000",
            "status": "failed",
            "error": {"code": "failed", "message": "first failed"},
        },
        {
            "scene_id": "scene_000001",
            "status": "cancelled",
            "error": {"code": "cancelled", "message": "second cancelled"},
        },
    ]
    _write_manifest(root, manifest)

    outcome = load_result_v2(root)

    assert outcome.status is LoadStatus.INVALID
    assert "at least one successful Scene" in outcome.reason


def test_partial_all_success_is_invalid(tmp_path: Path) -> None:
    root = write_golden_result_v2(tmp_path / "all-success", scene_count=2)
    manifest = _manifest(root)
    manifest["publication_state"] = "partial"
    manifest["scene_outcomes"] = [
        {"scene_id": scene["scene_id"], "status": "succeeded"}
        for scene in manifest["scenes"]
    ]
    _write_manifest(root, manifest)

    outcome = load_result_v2(root)

    assert outcome.status is LoadStatus.INVALID
    assert "failed or cancelled" in outcome.reason


def test_partial_success_outcomes_must_exactly_match_published_scenes(tmp_path: Path) -> None:
    root = _partial_root(tmp_path, "failed")
    manifest = _manifest(root)
    manifest["scene_outcomes"][0]["scene_id"] = "scene_wrong"
    _write_manifest(root, manifest)

    outcome = load_result_v2(root)

    assert outcome.status is LoadStatus.INVALID
    assert "correspond exactly" in outcome.reason


@pytest.mark.parametrize(
    "mutate",
    (
        lambda outcomes: outcomes.append(dict(outcomes[0])),
        lambda outcomes: outcomes[0].update({"status": "unknown"}),
        lambda outcomes: outcomes[-1].pop("error"),
        lambda outcomes: outcomes[0].update(
            {"error": {"code": "bad", "message": "success must not fail"}}
        ),
        lambda outcomes: outcomes[-1]["error"].update({"retryable": "yes"}),
    ),
)
def test_malformed_partial_outcomes_are_invalid(tmp_path: Path, mutate: Any) -> None:
    root = _partial_root(tmp_path, "failed")
    manifest = _manifest(root)
    mutate(manifest["scene_outcomes"])
    _write_manifest(root, manifest)

    outcome = load_result_v2(root)

    assert outcome.status is LoadStatus.INVALID


def test_partial_failed_scene_never_gets_fabricated_measurements(tmp_path: Path) -> None:
    root = _partial_root(tmp_path, "failed")
    outcome = load_result(root)
    assert isinstance(outcome.result, PartialResultV2)

    result = outcome.result
    published_scene_ids = {scene.scene_id for scene in result.scenes}
    failed_scene_ids = {item.scene_id for item in result.unsuccessful_scene_outcomes}

    assert published_scene_ids.isdisjoint(failed_scene_ids)
    assert failed_scene_ids == {"scene_000004"}
