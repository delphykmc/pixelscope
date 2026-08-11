from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelscope.core.comparison_set import ComparisonSet, ComparisonSetError, ComparisonSetSource
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.raw_profile import RawProfile


def _profile() -> RawProfile:
    return RawProfile(
        name="gray10",
        width=4,
        height=4,
        stride_bytes=8,
        bit_depth=10,
        channel_layout="GRAY",
        black_level=64,
        white_level=1023,
    )


def test_v1_round_trip_preserves_order_optional_identity_and_raw_profile(tmp_path: Path) -> None:
    first = tmp_path / "b.raw"
    second = tmp_path / "a.png"
    comparison_set = ComparisonSet(
        sources=(
            ComparisonSetSource(str(first), _profile().dict()),
            ComparisonSetSource(str(second)),
        ),
        active_path=str(second),
        primary_path=str(first),
        layout_mode="Multi View",
    )
    target = tmp_path / "set.pixelscope"
    repository = ComparisonSetRepository()

    repository.save(target, comparison_set)
    restored = repository.load(target)

    assert restored == comparison_set
    assert [source.path for source in restored.sources] == [str(first.resolve()), str(second.resolve())]
    assert RawProfile.parse_obj(restored.sources[0].raw_profile) == _profile()


def test_source_paths_are_normalized_to_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    comparison_set = ComparisonSet(sources=(ComparisonSetSource("folder/../image.png"),))
    assert comparison_set.sources[0].path == str((tmp_path / "image.png").resolve())


def test_duplicate_source_paths_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "image.png"
    with pytest.raises(ComparisonSetError, match="duplicate"):
        ComparisonSet(sources=(ComparisonSetSource(path), ComparisonSetSource(path)))


@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "kind"),
        ({"kind": "other", "schema_version": 1, "sources": []}, "kind"),
        ({"kind": "pixelscope-comparison-set", "schema_version": 2, "sources": []}, "schema"),
        ({"kind": "pixelscope-comparison-set", "schema_version": 1, "sources": []}, "sources"),
        ({"kind": "pixelscope-comparison-set", "schema_version": 1, "sources": [{"path": 3}]}, "path"),
        ({"kind": "pixelscope-comparison-set", "schema_version": 1, "sources": [{"path": "/x"}], "layout_mode": "Grid"}, "layout"),
    ],
)
def test_invalid_schema_is_rejected(payload: object, message: str) -> None:
    with pytest.raises(ComparisonSetError, match=message):
        ComparisonSetRepository().from_payload(payload)


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "broken.pixelscope"
    target.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ComparisonSetError, match="cannot read"):
        ComparisonSetRepository().load(target)


def test_unknown_fields_are_ignored_within_supported_schema(tmp_path: Path) -> None:
    source = str((tmp_path / "image.png").resolve())
    payload = {
        "kind": "pixelscope-comparison-set",
        "schema_version": 1,
        "sources": [{"path": source, "future_source_field": 7}],
        "layout_mode": "Auto",
        "future_top_level_field": {"value": True},
    }
    restored = ComparisonSetRepository().from_payload(payload)
    assert restored.sources == (ComparisonSetSource(source),)


def test_atomic_save_leaves_valid_json(tmp_path: Path) -> None:
    target = tmp_path / "set.pixelscope"
    comparison_set = ComparisonSet(sources=(ComparisonSetSource(tmp_path / "image.png"),))
    ComparisonSetRepository().save(target, comparison_set)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["kind"] == "pixelscope-comparison-set"
    assert payload["schema_version"] == 1
