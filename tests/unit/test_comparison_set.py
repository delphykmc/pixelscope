from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelscope.core.comparison_set import (
    ComparisonSetError,
    Session,
    SessionDifference,
    SessionSource,
)
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
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


def test_session_v1_round_trip_preserves_workspace_intent(tmp_path: Path) -> None:
    first = tmp_path / "b.raw"
    second = tmp_path / "a.png"
    third = tmp_path / "registered-only.png"
    session = Session(
        registered_sources=(
            SessionSource(str(first), _profile().dict()),
            SessionSource(str(second)),
            SessionSource(str(third)),
        ),
        selected_paths=(str(first), str(second)),
        page_anchor_path=str(first),
        active_path=str(second),
        primary_path=str(first),
        layout_mode="Multi View",
        roi=RoiBounds(1, 2, 3, 4),
        line=LineSelection(0, 1, 3, 1),
        display_gain=8.0,
        split_channels=False,
        difference=SessionDifference(
            str(first),
            str(second),
            channel="Gray",
            mode="Mask",
            threshold=12.5,
            gain=4,
            region="Active ROI",
        ),
    )
    target = tmp_path / "session.pixelscope"
    repository = ComparisonSetRepository()

    repository.save(target, session)
    restored = repository.load(target)

    assert restored == session
    assert restored.kind == "pixelscope-session"
    assert Path(restored.page_anchor_path or "").name == "b.raw"
    assert [Path(source.path).name for source in restored.registered_sources] == [
        "b.raw",
        "a.png",
        "registered-only.png",
    ]
    assert [Path(path).name for path in restored.selected_paths] == ["b.raw", "a.png"]
    assert RawProfile.parse_obj(restored.registered_sources[0].raw_profile) == _profile()


def test_difference_recipe_derives_page_anchor_when_active_is_derived(tmp_path: Path) -> None:
    paths = [tmp_path / f"image-{index}.png" for index in range(8)]
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        active_path=None,
        primary_path=None,
        difference=SessionDifference(str(paths[6]), str(paths[7])),
    )

    assert session.page_anchor_path == str(paths[6].resolve())
    assert ComparisonSetRepository().to_payload(session)["page_anchor_path"] == str(
        paths[6].resolve()
    )


def test_page_anchor_must_be_a_selected_member(tmp_path: Path) -> None:
    selected = tmp_path / "selected.png"
    other = tmp_path / "registered-only.png"
    with pytest.raises(ComparisonSetError, match="page anchor"):
        Session(
            registered_sources=(SessionSource(str(selected)), SessionSource(str(other))),
            selected_paths=(str(selected),),
            page_anchor_path=str(other),
        )


def test_writer_persists_recipe_not_difference_cache_or_result(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    session = Session(
        registered_sources=(SessionSource(str(a)), SessionSource(str(b))),
        selected_paths=(str(a), str(b)),
        difference=SessionDifference(str(a), str(b), mode="Absolute", threshold=3.0, gain=2),
    )

    payload = ComparisonSetRepository().to_payload(session)

    assert payload["kind"] == "pixelscope-session"
    assert payload["page_anchor_path"] == str(a.resolve())
    assert "difference" in payload
    assert "cache" not in payload
    assert "difference_map" not in payload
    assert "metrics" not in payload
    assert "workers" not in payload


def test_registered_and_selected_are_distinct_and_selected_must_be_subset(tmp_path: Path) -> None:
    registered = SessionSource(str(tmp_path / "registered.png"))
    with pytest.raises(ComparisonSetError, match="Selected source"):
        Session(
            registered_sources=(registered,),
            selected_paths=(str(tmp_path / "other.png"),),
        )


def test_session_allows_registered_workspace_with_zero_selected(tmp_path: Path) -> None:
    source = SessionSource(str(tmp_path / "registered.png"))
    session = Session(registered_sources=(source,))
    assert session.selected_paths == ()
    assert session.page_anchor_path is None
    assert session.active_path is None


def test_duplicate_registered_paths_are_rejected(tmp_path: Path) -> None:
    path = str(tmp_path / "image.png")
    with pytest.raises(ComparisonSetError, match="duplicate registered"):
        Session(
            registered_sources=(SessionSource(path), SessionSource(path)),
        )


def test_difference_sources_must_be_registered(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    with pytest.raises(ComparisonSetError, match="Difference source"):
        Session(
            registered_sources=(SessionSource(str(a)),),
            selected_paths=(str(a),),
            difference=SessionDifference(str(a), str(b)),
        )


def test_artifact_reader_rejects_relative_source_path() -> None:
    payload = {
        "kind": "pixelscope-session",
        "schema_version": 1,
        "registered_sources": [{"path": "images/a.png"}],
        "selected_paths": [],
    }
    with pytest.raises(ComparisonSetError, match="absolute path"):
        ComparisonSetRepository().from_payload(payload)


@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "schema"),
        ({"kind": "other", "schema_version": 1}, "kind"),
        (
            {
                "kind": "pixelscope-session",
                "schema_version": 2,
                "registered_sources": [],
            },
            "schema",
        ),
        (
            {
                "kind": "pixelscope-session",
                "schema_version": 1,
                "registered_sources": [],
            },
            "registered_sources",
        ),
        (
            {
                "kind": "pixelscope-session",
                "schema_version": 1,
                "registered_sources": [{"path": str(Path.cwd() / "x")}],
                "layout_mode": "Grid",
            },
            "layout",
        ),
    ],
)
def test_invalid_session_schema_is_rejected(payload: object, message: str) -> None:
    with pytest.raises(ComparisonSetError, match=message):
        ComparisonSetRepository().from_payload(payload)


def test_legacy_p4b_comparison_set_is_read_as_session(tmp_path: Path) -> None:
    first = str((tmp_path / "first.png").resolve())
    second = str((tmp_path / "second.png").resolve())
    payload = {
        "kind": "pixelscope-comparison-set",
        "schema_version": 1,
        "sources": [{"path": first}, {"path": second}],
        "active_path": second,
        "primary_path": first,
        "layout_mode": "Multi View",
    }

    session = ComparisonSetRepository().from_payload(payload)

    assert session.kind == "pixelscope-session"
    assert tuple(source.path for source in session.registered_sources) == (first, second)
    assert session.selected_paths == (first, second)
    assert session.page_anchor_path == second
    assert session.active_path == second
    assert session.primary_path == first


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "broken.pixelscope"
    target.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ComparisonSetError, match="cannot read"):
        ComparisonSetRepository().load(target)


def test_atomic_save_leaves_valid_session_json(tmp_path: Path) -> None:
    target = tmp_path / "session.pixelscope"
    session = Session(
        registered_sources=(SessionSource(str(tmp_path / "image.png")),),
    )
    ComparisonSetRepository().save(target, session)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["kind"] == "pixelscope-session"
    assert payload["schema_version"] == 1
