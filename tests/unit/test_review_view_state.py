"""W04 durable Review viewport is a strict, immutable, Qt-free value object."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from pixelscope.core.review_view_state import ReviewViewStateV1, ReviewViewportV1


KEYS = tuple(str(UUID(int=i + 1)) for i in range(6))


def make_state(*, count: int = 2, sync: bool = True) -> ReviewViewStateV1:
    keys = KEYS[:count]
    return ReviewViewStateV1(
        reference_source_key=keys[0],
        page_source_keys=keys,
        active_source_key=keys[-1],
        primary_source_key=keys[0],
        layout_kind="Grid 2x2",
        presentation_mode="originals",
        sync_enabled=sync,
        center_ref_xy=(32.5, 22.5),
        physical_scale=2.0,
        reference_shape=(64, 96),
        source_shapes_ref={key: (64, 96) for key in keys},
        per_source=(
            {} if sync else {
                key: ReviewViewportV1((20.5 + i, 30.5 + i), 1.0 + i)
                for i, key in enumerate(keys)
            }
        ),
        visible_bounds_ref=(-32.0, -30.0, 98.0, 75.0),
    )


@pytest.mark.parametrize("count", [1, 2, 4, 6])
@pytest.mark.parametrize("sync", [False, True])
def test_strict_round_trip_and_deep_immutability(count: int, sync: bool) -> None:
    state = make_state(count=count, sync=sync)
    wire = state.to_dict()
    assert ReviewViewStateV1.from_dict(wire) == state
    assert wire["page_source_keys"] == list(KEYS[:count])
    with pytest.raises(TypeError):
        state.per_source[KEYS[0]] = ReviewViewportV1((2.0, 3.0), 1.0)  # type: ignore[index]
    with pytest.raises(TypeError):
        state.source_shapes_ref[KEYS[0]] = (1, 1)  # type: ignore[index]
    wire["source_shapes_ref"][KEYS[0]] = [1, 1]
    assert state.source_shapes_ref[KEYS[0]] == (64, 96)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reference_source_key", KEYS[5]),
        ("active_source_key", KEYS[5]),
        ("primary_source_key", KEYS[5]),
        ("layout_kind", "Unknown"),
        ("presentation_mode", "unknown"),
        ("sync_enabled", 1),
        ("center_ref_xy", (float("nan"), 2.0)),
        ("center_ref_xy", (1.0, float("inf"))),
        ("physical_scale", 0),
        ("physical_scale", float("-inf")),
        ("reference_shape", (64, 0)),
        ("page_source_keys", (KEYS[0], KEYS[0])),
        ("page_source_keys", ()),
        ("page_source_keys", KEYS + (str(UUID(int=9)),)),
        ("visible_bounds_ref", (3, 1, 2, 4)),
        ("schema_version", 2),
    ],
)
def test_invalid_state_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        replace(make_state(), **{field: value})


def test_invalid_unsynced_shape_and_viewports_rejected() -> None:
    state = make_state(sync=False)
    with pytest.raises(ValueError):
        replace(state, per_source={KEYS[0]: ReviewViewportV1((1, 1), 1)})
    with pytest.raises(ValueError):
        replace(state, source_shapes_ref={KEYS[0]: (64, 96)})
    with pytest.raises(ValueError):
        replace(state, reference_shape=(63, 96))
    with pytest.raises(ValueError):
        replace(state, sync_enabled=True)


def test_strict_wire_no_unknown_fields_or_future_schema() -> None:
    wire = make_state().to_dict()
    with pytest.raises(ValueError):
        ReviewViewStateV1.from_dict({**wire, "source_alias": "not identity"})
    with pytest.raises(ValueError):
        ReviewViewStateV1.from_dict({**wire, "schema_version": 2})
    wire["per_source"] = {KEYS[0]: {"physical_scale": 1, "center_ref_xy": [1, 1], "qt": 1}}
    with pytest.raises(ValueError):
        ReviewViewStateV1.from_dict(wire)


def test_uuid_is_canonical_not_display_name_or_runtime_document_id() -> None:
    state = make_state()
    for wrong in ("file.png", "/home/user/file.png", str(UUID(int=1)).upper()):
        with pytest.raises(ValueError):
            replace(state, reference_source_key=wrong)
