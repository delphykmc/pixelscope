"""W04 View State capture/restore uses the W01 measured physical-pixel oracle."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import numpy as np
import pytest

from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.multi_compare_view import MultiCompareView
from pixelscope.ui.review_view_state_adapter import (
    VerifiedViewSource,
    capture_review_view_state,
    restore_review_view_state,
)

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _fixture(qtbot: object, count: int) -> tuple[MultiCompareView, list[ImageDocument], tuple[str, ...]]:
    multi = MultiCompareView()
    qtbot.addWidget(multi)  # type: ignore[attr-defined]
    multi.resize(1203, 701)
    multi.set_capacity(2 if count == 1 else count)
    docs = [
        ImageDocument.from_array(
            np.full((128, 192, 3), index, dtype=np.uint8), f"{index}.png"
        )
        for index in range(count)
    ]
    multi.set_documents(docs, 0, count, None, None)
    multi.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not multi._layout_refit_active
        and all(viewer.measure_physical_zoom().valid for viewer in multi.occupied_viewers),
        timeout=3000,
    )
    keys = tuple(str(UUID(int=index + 1)) for index in range(count))
    return multi, docs, keys


def _capture(
    multi: MultiCompareView, docs: list[ImageDocument], keys: tuple[str, ...]
):
    result = capture_review_view_state(
        multi,
        {document.document_id: key for document, key in zip(docs, keys, strict=True)},
        reference_source_key=keys[0],
        primary_source_key=keys[0],
        presentation_mode="originals",
    )
    assert result.available, result.reason
    assert result.state is not None
    return result.state


def _bindings(docs: list[ImageDocument], keys: tuple[str, ...]):
    return {
        key: VerifiedViewSource(document, document.generation, True)
        for key, document in zip(keys, docs, strict=True)
    }


def _center(viewer: object) -> tuple[float, float]:
    ranges = viewer.view_box.viewRange()  # type: ignore[attr-defined]
    return ((ranges[0][0] + ranges[0][1]) / 2, (ranges[1][0] + ranges[1][1]) / 2)


@pytest.mark.parametrize("count", [1, 2, 4, 6])
@pytest.mark.parametrize("sync", [False, True])
def test_capture_pan_zoom_restore_exact_physical_scale_and_source_identity(
    qtbot: object, count: int, sync: bool
) -> None:
    multi, docs, keys = _fixture(qtbot, count)
    multi.set_sync_enabled(sync)
    multi.zoom_100_percent()
    if sync:
        assert multi.visible_viewers[0].set_physical_zoom(200, (70, 60)).achieved
    else:
        for index, viewer in enumerate(multi.occupied_viewers):
            assert viewer.set_physical_zoom(
                100.0 + index * 40.0, (52 + index * 3, 62 + index * 2)
            ).achieved
    state = _capture(multi, docs, keys)
    assert state.sync_enabled is sync
    assert state.per_source.keys() == set(keys) if not sync else len(state.per_source) == 0

    for viewer in multi.occupied_viewers:
        assert viewer.set_physical_zoom(400.0, (95.0, 80.0)).achieved
    epoch = multi._review_restore_epoch + 1
    assert multi.begin_review_restore(epoch)
    result = restore_review_view_state(
        multi, state, _bindings(docs, keys), epoch=epoch, presentation_mode="originals"
    )
    assert result.applied, result

    for index, viewer in enumerate(multi.occupied_viewers):
        target = (
            state.per_source[keys[index]]
            if not sync else state
        )
        assert viewer.measure_physical_zoom().percent == pytest.approx(
            target.physical_scale * 100, rel=0.005
        )
        assert _center(viewer) == pytest.approx(target.center_ref_xy, abs=0.5)


def test_slot_reorder_restores_by_document_identity_not_ordinal(qtbot: object) -> None:
    multi, docs, keys = _fixture(qtbot, 2)
    multi.set_sync_enabled(False)
    for viewer, center in zip(multi.occupied_viewers, ((30, 40), (80, 90)), strict=True):
        assert viewer.set_physical_zoom(150, center).achieved
    state = _capture(multi, docs, keys)
    multi.set_documents(list(reversed(docs)), 0, 2, None, None)
    multi.focus_document_id = docs[0].document_id
    epoch = multi._review_restore_epoch + 1
    assert multi.begin_review_restore(epoch)
    result = restore_review_view_state(
        multi, state, _bindings(docs, keys), epoch=epoch, presentation_mode="originals"
    )
    assert result.applied, result
    for viewer in multi.occupied_viewers:
        assert viewer.document is not None
        key = next(key for document, key in zip(docs, keys, strict=True)
                   if document is viewer.document)
        assert _center(viewer) == pytest.approx(state.per_source[key].center_ref_xy, abs=0.5)


@pytest.mark.parametrize("failure", ["missing", "unverified", "generation", "bounds", "replaced"])
def test_restore_fails_closed_without_modifying_view(
    qtbot: object, failure: str
) -> None:
    multi, docs, keys = _fixture(qtbot, 2)
    multi.zoom_100_percent()
    state = _capture(multi, docs, keys)
    before = [viewer.view_box.viewRange() for viewer in multi.occupied_viewers]
    bindings = _bindings(docs, keys)
    if failure == "missing":
        bindings.pop(keys[1])
    elif failure == "unverified":
        bindings[keys[1]] = VerifiedViewSource(docs[1], docs[1].generation, False)
    elif failure == "generation":
        bindings[keys[1]] = VerifiedViewSource(docs[1], docs[1].generation + 1, True)
    elif failure == "bounds":
        state = replace(state, source_shapes_ref={keys[0]: (128, 192), keys[1]: (1, 1)})
    elif failure == "replaced":
        other = ImageDocument.from_array(np.zeros((128, 192, 3), dtype=np.uint8), "replace.png")
        other.document_id = docs[1].document_id  # same transient ID is NOT same source
        bindings[keys[1]] = VerifiedViewSource(other, other.generation, True)
    epoch = multi._review_restore_epoch + 1
    assert multi.begin_review_restore(epoch)
    result = restore_review_view_state(
        multi, state, bindings, epoch=epoch, presentation_mode="originals"
    )
    assert result.status in ("pending", "unavailable")
    for viewer, previous in zip(multi.occupied_viewers, before, strict=True):
        assert viewer.view_box.viewRange() == previous


def test_pending_epoch_user_navigation_and_new_epoch(qtbot: object) -> None:
    multi, docs, keys = _fixture(qtbot, 2)
    multi.zoom_100_percent()
    state = _capture(multi, docs, keys)
    epoch = multi._review_restore_epoch + 1
    assert multi.begin_review_restore(epoch)
    multi.visible_viewers[0].view_box.user_navigation_started.emit()
    stale = restore_review_view_state(
        multi, state, _bindings(docs, keys), epoch=epoch, presentation_mode="originals"
    )
    assert stale.status == "interrupted"
    second_epoch = epoch + 1
    assert multi.begin_review_restore(second_epoch)
    assert restore_review_view_state(
        multi, state, _bindings(docs, keys), epoch=second_epoch, presentation_mode="originals"
    ).applied
    assert not restore_review_view_state(
        multi, state, _bindings(docs, keys), epoch=second_epoch, presentation_mode="originals"
    ).applied


def test_shutdown_revokes_pending_epoch(qtbot: object) -> None:
    multi, docs, keys = _fixture(qtbot, 2)
    state = _capture(multi, docs, keys)
    epoch = multi._review_restore_epoch + 1
    assert multi.begin_review_restore(epoch)
    multi.shutdown()
    assert restore_review_view_state(
        multi, state, _bindings(docs, keys), epoch=epoch, presentation_mode="originals"
    ).status == "interrupted"
