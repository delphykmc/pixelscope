from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.multi_compare_view import MultiCompareView


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()


def _documents(count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((24, 36, 3), index * 10, dtype=np.uint8),
            f"p1d-{index + 1}.png",
        )
        for index in range(count)
    ]


@pytest.mark.parametrize("count", range(1, 7))
def test_pin_control_describes_first_tile_and_is_visible_for_multi_view(
    qtbot: object,
    count: int,
) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = _documents(count)
    view.set_capacity(2 if count <= 2 else 4 if count <= 4 else 6)
    view.set_layout_kind("Multi View", documents[0].document_id)
    view.set_documents(documents, 0, count, None, None)

    for viewer in view.occupied_viewers:
        assert viewer.header.focus.isHidden() is (count == 1)
        assert viewer.header.focus.toolTip() in {
            "Pin to first tile",
            "First tile is pinned",
        }


@pytest.mark.parametrize("count", (2, 4, 6))
def test_even_view_pin_promotes_display_only_and_preserves_view_state(
    qtbot: object,
    count: int,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(count)
    for document in documents:
        window.add_document(document, select=False)
    selected_ids = [document.document_id for document in documents]
    window._select_document_ids(selected_ids)
    window.set_layout_mode("Multi View")
    viewer_ids = tuple(id(viewer) for viewer in window.multi_compare_view.viewers)
    logical_ids = tuple(window.documents)

    window.multi_compare_view.viewers[0].view_box.setRange(
        xRange=(3.0, 21.0),
        yRange=(2.0, 14.0),
        padding=0,
    )
    before = window.multi_compare_view.capture_view_state()
    window._set_focus_document(documents[-1])
    after = window.multi_compare_view.capture_view_state()

    assert window.multi_compare_view.viewers[0].document is documents[-1]
    assert [document.document_id for document in window.selected_documents] == selected_ids
    assert tuple(window.documents) == logical_ids
    assert tuple(id(viewer) for viewer in window.multi_compare_view.viewers) == viewer_ids
    assert before.ranges is not None and after.ranges is not None
    assert np.allclose(after.ranges, before.ranges)
    window.close()


def test_target_layout_is_applied_before_first_document_binding(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = _documents(4)
    view.set_capacity(4)
    view.set_documents(documents, 0, 4, None, None)

    observations: list[tuple[tuple[int, int, int, int], tuple[bool, ...], bool]] = []
    original_set_document = view.viewers[0].set_document

    def record_first_binding(document: ImageDocument | None, fit: bool = True) -> None:
        if document is not None:
            observations.append(
                (
                    view._layout.getItemPosition(view._layout.indexOf(view.viewers[0])),
                    tuple(viewer.isHidden() for viewer in view.visible_viewers),
                    view.updatesEnabled(),
                )
            )
        original_set_document(document, fit=fit)

    monkeypatch.setattr(view.viewers[0], "set_document", record_first_binding)
    view.set_documents([documents[0]], 0, 1, None, None)

    assert observations == [((0, 0, 1, 1), (False, True, True, True), False)]
    assert view.updatesEnabled()
    assert view.occupied_viewers == [view.viewers[0]]


def test_atomic_replacement_preserves_preexisting_updates_disabled_state(
    qtbot: object,
) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = _documents(4)
    view.set_capacity(4)
    view.setDocuments = view.set_documents  # type: ignore[attr-defined]
    view.setUpdatesEnabled(False)

    view.set_documents(documents, 0, 4, None, None)

    assert not view.updatesEnabled()
