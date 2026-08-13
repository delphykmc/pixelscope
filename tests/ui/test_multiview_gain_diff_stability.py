from __future__ import annotations

import numpy as np

from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.display_gain import display_gain_state
from pixelscope.ui.multi_compare_view import MultiCompareView


def _rgb_document(name: str, value: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((64, 64, 3), value, dtype=np.uint8),
        name,
        channel_layout="RGB",
    )


def test_gain_requests_survive_diff_insert_remove_without_source_viewer_churn(
    qtbot: object,
) -> None:
    state = display_gain_state()
    state.reset()
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    sources = [_rgb_document(f"source-{index}.png", 20 + index) for index in range(4)]
    difference = ImageDocument.from_array(
        np.zeros((64, 64), dtype=np.uint8),
        "Difference",
        channel_layout="DIFFERENCE",
    )

    view.set_capacity(4)
    view.show()
    view.set_documents(sources, 0, len(sources), None, None)
    state.set_gain(2.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_gain == 2.0 and viewer._display_preview_worker is None
            for viewer in view.occupied_viewers
        ),
        timeout=3000,
    )

    source_viewers = {
        document.document_id: next(
            viewer for viewer in view.occupied_viewers if viewer.document is document
        )
        for document in sources
    }
    viewer_inventory = tuple(view.viewers)
    request_serials = {
        document_id: viewer._display_preview_request_serial
        for document_id, viewer in source_viewers.items()
    }

    view.set_capacity(6)
    with_difference = [sources[0], difference, *sources[1:]]
    view.set_documents(
        with_difference,
        0,
        len(sources),
        None,
        None,
        preserve_view=True,
    )

    assert tuple(view.viewers) == viewer_inventory
    assert [viewer.document for viewer in view.occupied_viewers] == with_difference
    for document in sources:
        viewer = next(
            candidate for candidate in view.occupied_viewers if candidate.document is document
        )
        assert viewer is source_viewers[document.document_id]
        assert viewer._display_preview_request_serial == request_serials[document.document_id]
        assert viewer._displayed_gain == 2.0

    view.set_capacity(4)
    view.set_documents(
        sources,
        0,
        len(sources),
        None,
        None,
        preserve_view=True,
    )

    assert tuple(view.viewers) == viewer_inventory
    assert [viewer.document for viewer in view.occupied_viewers] == sources
    for document in sources:
        viewer = next(
            candidate for candidate in view.occupied_viewers if candidate.document is document
        )
        assert viewer is source_viewers[document.document_id]
        assert viewer._display_preview_request_serial == request_serials[document.document_id]
        assert viewer._displayed_gain == 2.0

    view.close()
    state.reset()


def test_difference_presentation_does_not_change_logical_source_slots(qtbot: object) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    sources = [_rgb_document(f"source-{index}.png", 20 + index) for index in range(6)]
    difference = ImageDocument.from_array(
        np.zeros((64, 64), dtype=np.uint8),
        "Difference",
        channel_layout="DIFFERENCE",
    )
    logical_slots = {document.document_id: index + 1 for index, document in enumerate(sources)}

    view.set_capacity(6)
    view.show()
    view.set_documents(sources, 0, len(sources), None, None, slot_by_id=logical_slots)
    before = {
        viewer.document.document_id: viewer._slot
        for viewer in view.occupied_viewers
        if viewer.document is not None
    }

    presented = [difference, *sources[:5]]
    view.set_documents(
        presented,
        0,
        len(sources),
        None,
        None,
        preserve_view=True,
        slot_by_id=logical_slots,
    )

    after = {
        viewer.document.document_id: viewer._slot
        for viewer in view.occupied_viewers
        if viewer.document is not None and viewer.document is not difference
    }
    assert before == logical_slots
    assert after == {document.document_id: logical_slots[document.document_id] for document in sources[:5]}
    view.close()
