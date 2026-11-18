from __future__ import annotations

import numpy as np
import pytest

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.design_tokens import tile_style
from pixelscope.ui.image_viewer import ImageViewer

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_active_style_initializes_and_only_real_changes_update_cursor_and_border(
    qtbot: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []
    original = ImageViewer.setStyleSheet

    def record_style(viewer: ImageViewer, style: str) -> None:
        calls.append(viewer._active)
        original(viewer, style)

    monkeypatch.setattr(ImageViewer, "setStyleSheet", record_style)
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    assert calls == [False]
    assert viewer.styleSheet() == tile_style(False)
    assert viewer._vertical_cursor.pen.color().alpha() == 55
    assert viewer._horizontal_cursor.pen.color().alpha() == 55

    viewer.set_active(False)
    viewer.set_active(True)
    viewer.set_active(True)
    assert calls == [False, True]
    assert viewer.styleSheet() == tile_style(True)
    assert viewer._vertical_cursor.pen.color().alpha() == 150
    assert viewer._horizontal_cursor.pen.color().alpha() == 150

    viewer.set_active(False)
    viewer.set_active(False)
    assert calls == [False, True, False]
    assert viewer.styleSheet() == tile_style(False)
    assert viewer._vertical_cursor.pen.color().alpha() == 55
    assert viewer._horizontal_cursor.pen.color().alpha() == 55


def test_pick_property_changes_repolish_but_unchanged_review_sync_does_not(
    qtbot: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    documents = [
        ImageDocument.from_array(np.full((8, 8), value, dtype=np.uint8), str(value))
        for value in (10, 20)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    review = window.review_selection_controller
    viewer = window.multi_compare_view.occupied_viewers[0]
    assert viewer.document is not None
    document_id = viewer.document.document_id
    calls: list[bool] = []
    original = ImageViewer.setStyleSheet

    def record_style(target: ImageViewer, style: str) -> None:
        if target is viewer:
            calls.append(bool(target.property("reviewPicked")))
        original(target, style)

    monkeypatch.setattr(ImageViewer, "setStyleSheet", record_style)
    review._sync_all()
    review._sync_all()
    assert calls == []
    review.state.enter([document.document_id for document in documents])
    review.state.set_picked(document_id, True)
    review._sync_all()
    review._sync_all()
    assert calls == [True]
    assert viewer.header.pick.isChecked()
    review.state.set_picked(document_id, False)
    review._sync_all()
    review._sync_all()
    assert calls == [True, False]
    assert not viewer.header.pick.isChecked()
    window.close()


@pytest.mark.parametrize(
    ("source_count", "show_difference"), [(2, False), (3, False), (6, False), (2, True), (4, True)]
)
def test_primary_reorder_keeps_sources_analysis_and_tile_styles(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    source_count: int,
    show_difference: bool,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    documents = [
        ImageDocument.from_array(np.full((8, 8, 3), value, dtype=np.uint8), str(value))
        for value in range(source_count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window.show()
    analysis = window.comparison_analysis_panel
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: bool(analysis.last_results)
        and analysis._worker is None
        and not analysis._refresh_timer.isActive()
    )
    if show_difference:
        window.difference_panel.calculate_difference()
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: window._difference_document is not None
            and window.difference_panel._worker is None
            and window.difference_panel._preview_worker is None
        )

    view = window.multi_compare_view
    source_viewers = {
        viewer.document.document_id: viewer
        for viewer in view.occupied_viewers
        if viewer.document is not None
    }
    source_state = [
        (document.source, document.preview, document.generation) for document in documents
    ]
    results = analysis.last_results
    signature = analysis._request_signature
    styles: list[ImageViewer] = []
    original = ImageViewer.setStyleSheet

    def record_style(viewer: ImageViewer, style: str) -> None:
        styles.append(viewer)
        original(viewer, style)

    def unexpected_work(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("resident Primary reorder must not upload or dispatch numerical work")

    monkeypatch.setattr(ImageViewer, "setStyleSheet", record_style)
    monkeypatch.setattr(ImageViewer, "_upload_preview", unexpected_work)
    monkeypatch.setattr(analysis._pool, "start", unexpected_work)
    monkeypatch.setattr(window._load_pool, "start", unexpected_work)
    for index in range(10):
        primary = documents[index % source_count]
        window._set_focus_document(primary)
        assert view.occupied_viewers[0].document is primary
        assert window._focus_document_id == primary.document_id
        assert analysis.last_results is results
        assert analysis._request_signature == signature
        assert not analysis._refresh_timer.isActive()
        for viewer in view.occupied_viewers:
            assert viewer.document is not None
            assert source_viewers[viewer.document.document_id] is viewer
    assert styles == []
    for document, (source, preview, generation) in zip(documents, source_state, strict=True):
        assert document.source is source
        assert document.preview is preview
        assert document.generation == generation
    window.close()
