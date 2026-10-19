from __future__ import annotations

from pathlib import Path
from threading import Event, get_ident

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QDropEvent

from pixelscope.app.bootstrap import (
    compose_main_window_presentation as _compose_main_window_presentation,
)
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.quick_compare import QuickCompareController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


@pytest.mark.parametrize("kind", ["files", "folder", "mixed"])
def test_image_drop_classifies_network_paths_only_on_worker(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str
) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    inside = folder / "inside.png"
    direct = tmp_path / "direct.png"
    assert cv2.imwrite(str(inside), np.full((8, 8), 10, dtype=np.uint8))
    assert cv2.imwrite(str(direct), np.full((8, 8), 20, dtype=np.uint8))
    paths = {"files": [direct], "folder": [folder], "mixed": [folder, direct]}[kind]
    window, controller = _window(qtbot)
    seed = ImageDocument.from_array(np.zeros((8, 8), dtype=np.uint8), "seed")
    window.add_document(seed, select=True)
    gui_thread = get_ident()
    entered = Event()
    release = Event()
    original = Path.is_dir

    def checked_is_dir(path: Path) -> bool:
        if path in paths:
            assert get_ident() != gui_thread, "SMB classification ran on GUI thread"
            entered.set()
            assert release.wait(5), "test did not release discovery"
        return original(path)

    monkeypatch.setattr(Path, "is_dir", checked_is_dir)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    event = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    progressed: list[bool] = []
    try:
        assert controller.eventFilter(window.central_stack, event)
        assert event.isAccepted()
        qtbot.waitUntil(entered.is_set, timeout=3000)  # type: ignore[attr-defined]
        QTimer.singleShot(0, lambda: progressed.append(True))
        qtbot.waitUntil(lambda: bool(progressed), timeout=3000)  # type: ignore[attr-defined]
        assert _ids(window) == [seed.document_id]
    finally:
        release.set()
    registration = window.large_folder_registration_controller
    qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)  # type: ignore[attr-defined]
    selected = window.selected_documents
    if kind == "folder":
        assert _ids(window) == [seed.document_id]
    else:
        assert len(selected) == 2
        assert selected[0] is seed
        assert selected[1].source_path == direct.resolve()
    assert (
        inside.resolve() in [doc.source_path for doc in window.documents.values()]
        or kind == "files"
    )
    window.close()


def _window(qtbot: object) -> tuple[MainWindow, QuickCompareController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.quick_compare_controller
    assert isinstance(controller, QuickCompareController)
    return window, controller


def _document(name: str, value: int, tmp_path: Path) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((6, 8), value, dtype=np.uint8),
        name,
        source_path=tmp_path / name,
    )


def _add(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)


def test_window_close_revokes_pending_passive_difference(qtbot: object) -> None:
    window, controller = _window(qtbot)
    controller._schedule_difference(("a", "b"))
    assert controller._difference_retry_timer.isActive()
    window.close()
    assert not controller._difference_retry_timer.isActive()
    assert controller._pending_difference_pair is None
    assert controller._protected_difference_pair is None


def _ids(window: MainWindow) -> list[str]:
    return [document.document_id for document in window.selected_documents]


def _wait_for_difference(
    qtbot: object,
    window: MainWindow,
    pair: tuple[str, str],
) -> None:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.difference_panel.has_cached_map()
        and (selected := window.difference_panel.selected_documents()) is not None
        and tuple(document.document_id for document in selected) == pair
        and window.diff_action.isEnabled(),
        timeout=5000,
    )
    assert not window.diff_action.isChecked()
    assert window._difference_source_ids is None
    assert window.central_stack.updatesEnabled()


def test_sequential_quick_drop_is_additive_and_second_drop_calculates_difference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 20, tmp_path)
    third = _document("c.png", 30, tmp_path)
    _add(window, [first, second, third])

    controller._apply_registered_drop([first.document_id])
    assert _ids(window) == [first.document_id]
    assert window._difference_source_ids is None

    controller._apply_registered_drop([second.document_id])
    _wait_for_difference(qtbot, window, (first.document_id, second.document_id))
    assert _ids(window) == [first.document_id, second.document_id]

    controller._apply_registered_drop([third.document_id])
    assert _ids(window) == [first.document_id, second.document_id, third.document_id]
    assert not window.diff_action.isChecked()
    assert window.difference_panel.has_cached_map()
    window.close()


def test_two_file_batch_pairs_the_dropped_sources_without_retargeting_existing_difference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [
        _document(f"{name}.png", value, tmp_path)
        for name, value in zip("abc", (1, 2, 3), strict=True)
    ]
    _add(window, documents)

    controller._apply_registered_drop([documents[0].document_id])
    controller._apply_registered_drop([documents[1].document_id, documents[2].document_id])
    _wait_for_difference(
        qtbot,
        window,
        (documents[1].document_id, documents[2].document_id),
    )
    assert _ids(window) == [document.document_id for document in documents]
    window.close()


def test_three_file_batch_is_additive_without_automatic_difference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"{index}.png", index, tmp_path) for index in range(3)]
    _add(window, documents)

    controller._apply_registered_drop([document.document_id for document in documents])

    assert _ids(window) == [document.document_id for document in documents]
    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    window.close()


def test_ordinary_two_source_selection_remains_passive(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _controller = _window(qtbot)
    first = _document("a.png", 1, tmp_path)
    second = _document("b.png", 2, tmp_path)
    _add(window, [first, second])

    window._select_document_ids([first.document_id, second.document_id])

    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    window.close()


def test_quick_compare_drop_target_is_limited_to_image_presentation_surface(
    qtbot: object,
) -> None:
    window, controller = _window(qtbot)

    assert controller._is_image_surface(window.central_stack)
    assert controller._is_image_surface(window.viewer._graphics.viewport())
    assert not controller._is_image_surface(window.document_list)
    window.close()


def test_three_view_defaults_equal_and_user_can_switch_focus_without_state_change(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"{index}.png", index, tmp_path) for index in range(3)]
    _add(window, documents)
    window._select_document_ids([document.document_id for document in documents])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    roi = RoiBounds(1, 1, 4, 3)
    line = LineSelection(0, 0, 5, 4)
    assert window._shared_roi_changed(roi)
    window._shared_line_changed(line)

    authority = (
        tuple(_ids(window)),
        window._focus_document_id,
        window._active_document_id,
        window._shared_roi,
        window._shared_line,
    )
    equal_geometry = window.multi_compare_view._fixed_geometry(3)
    assert equal_geometry == (
        ((0, 0, 1, 1), (0, 1, 1, 1), (0, 2, 1, 1)),
        (1,),
        (1, 1, 1),
    )
    assert not controller.three_view_group.isVisible()
    assert window.issue77_ui_design_followup.three_view_button.isEnabled()

    controller.set_three_view_variant("Focus")

    assert window.multi_compare_view._fixed_geometry(3) == controller._original_fixed_geometry(3)
    assert authority == (
        tuple(_ids(window)),
        window._focus_document_id,
        window._active_document_id,
        window._shared_roi,
        window._shared_line,
    )
    window.close()


def test_three_view_difference_defaults_focus_and_other_geometries_are_unchanged(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 1, tmp_path)
    second = _document("b.png", 9, tmp_path)
    _add(window, [first, second])

    controller._apply_registered_drop([first.document_id, second.document_id])
    _wait_for_difference(qtbot, window, (first.document_id, second.document_id))
    window.diff_action.setChecked(True)

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.multi_compare_view._document_count == 3,
        timeout=3000,
    )
    assert controller._effective_three_view_variant() == "Focus"
    assert window.multi_compare_view._fixed_geometry(3) == controller._original_fixed_geometry(3)
    for count in (4, 5, 6):
        assert window.multi_compare_view._fixed_geometry(
            count
        ) == controller._original_fixed_geometry(count)
    window.close()


def test_image_surface_reopen_uses_shared_registration_and_refresh(
    qtbot: object,
    tmp_path: Path,
) -> None:
    path = tmp_path / "surface-refresh.png"
    assert cv2.imwrite(str(path), np.full((24, 32), 17, dtype=np.uint8))
    window, controller = _window(qtbot)
    registration = window.large_folder_registration_controller

    assert controller.handle_image_drop([path])
    assert registration.progress.phase == "scanning"
    qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)  # type: ignore[attr-defined]
    document_id = next(iter(window.documents))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].source is not None,
        timeout=3000,
    )
    first = window.documents[document_id]
    assert first.source is not None
    first_generation = first.generation
    first_source = first.source.copy()

    assert cv2.imwrite(str(path), np.full((24, 32), 219, dtype=np.uint8))
    assert controller.handle_image_drop([path])
    assert registration.progress.phase == "scanning"
    qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].source is not None
        and window.documents[document_id].generation > first_generation,
        timeout=3000,
    )

    refreshed = window.documents[document_id]
    assert refreshed.source is not None
    assert not np.array_equal(refreshed.source, first_source)
    assert np.all(refreshed.source == 219)
    assert window.viewer.document is refreshed
    assert len(window.documents) == 1
    window.close()


def test_cached_quick_difference_is_hidden_until_explicit_user_action(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    a = _document("manual-a.png", 3, tmp_path)
    b = _document("manual-b.png", 11, tmp_path)
    _add(window, [a, b])

    controller._apply_registered_drop([a.document_id])
    controller._apply_registered_drop([b.document_id])
    assert window.central_stack.updatesEnabled()
    assert not window.diff_action.isChecked()
    _wait_for_difference(qtbot, window, (a.document_id, b.document_id))
    assert window.multi_compare_view._document_count == 2

    def unexpected_map_recalculation(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("displaying cached Diff must not recalculate map")

    monkeypatch.setattr(
        window.difference_panel, "calculate_difference", unexpected_map_recalculation
    )
    window.diff_action.setChecked(True)
    assert window.diff_action.isChecked()
    assert window._difference_source_ids == (a.document_id, b.document_id)
    assert window.central_stack.updatesEnabled()
    window.close()


def test_files_drop_two_images_caches_diff_without_auto_display(
    qtbot: object, tmp_path: Path
) -> None:
    paths = [tmp_path / "files-first.png", tmp_path / "files-second.png"]
    for index, path in enumerate(paths):
        assert cv2.imwrite(str(path), np.full((20, 24), 40 + index, dtype=np.uint8))

    window, _controller = _window(qtbot)
    registration = window.large_folder_registration_controller
    window.document_list.paths_dropped.emit(paths)
    qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            document.source is not None for document in window.current_comparison_documents()
        )
        and len(window.current_comparison_documents()) == 2,
        timeout=5000,
    )
    pair = tuple(document.document_id for document in window.current_comparison_documents())
    assert len(pair) == 2
    _wait_for_difference(qtbot, window, pair)
    assert window._difference_source_ids is None
    assert window.central_stack.updatesEnabled()
    window.close()


def test_calculate_reuses_cached_diff_after_hide_and_show(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window, controller = _window(qtbot)
    a = _document("cached-a.png", 10, tmp_path)
    b = _document("cached-b.png", 40, tmp_path)
    _add(window, [a, b])
    controller._apply_registered_drop([a.document_id, b.document_id])
    _wait_for_difference(qtbot, window, (a.document_id, b.document_id))
    panel = window.difference_panel
    assert panel.last_result is not None
    baseline_map = panel.cached_result_for_current()

    def unexpected_map_compute(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("cached Difference must not recompute numerical map")

    monkeypatch.setattr(
        "pixelscope.ui.difference_panel.compact_absolute_difference",
        unexpected_map_compute,
    )

    with qtbot.waitSignal(panel.result_ready, timeout=5000):  # type: ignore[attr-defined]
        panel.calculate.click()
    assert panel._worker is None
    assert panel.cached_result_for_current() is baseline_map
    assert window.diff_action.isChecked()
    difference = window._difference_document
    assert difference is not None
    generation = difference.generation
    window.diff_action.setChecked(False)
    assert not window.diff_action.isChecked()
    toggles: list[bool] = []
    window.diff_action.toggled.connect(toggles.append)
    with qtbot.waitSignal(panel.result_ready, timeout=5000):  # type: ignore[attr-defined]
        panel.calculate.click()
    assert panel._worker is None
    assert panel.cached_result_for_current() is baseline_map
    assert window.diff_action.isChecked()
    # A warm Calculate must use the same toolbar toggle path as manual Diff,
    # not rebuild a separate Difference presentation or discard its caches.
    assert toggles == [True]
    assert window._difference_document is difference
    assert difference.generation == generation

    window.diff_action.setChecked(False)
    window.diff_action.setChecked(True)
    assert window._difference_document is difference
    assert difference.generation == generation
    window.close()


def test_calculate_promotes_running_passive_diff_without_new_worker(
    qtbot: object, tmp_path: Path
) -> None:
    window, _controller = _window(qtbot)
    a = _document("ongoing-a.png", 10, tmp_path)
    b = _document("ongoing-b.png", 20, tmp_path)
    _add(window, [a, b])
    window._select_document_ids([a.document_id, b.document_id])
    panel = window.difference_panel
    key = panel._cache_key()
    metric_key = panel._metric_key()
    assert key is not None and metric_key is not None

    class PendingWorker:
        task_id = "test-existing-worker"

        def cancel(self) -> None:
            pass

    worker = PendingWorker()
    panel._worker = worker  # type: ignore[assignment]
    panel._worker_key = (key, metric_key)
    panel.calculate_difference(publish_result=True)
    assert panel._worker is worker
    assert panel._presentation_map_pairs[worker.task_id] == (a.document_id, b.document_id)
    panel._worker = None
    panel._worker_key = None
    panel._presentation_map_pairs.pop(worker.task_id, None)
    window.close()
