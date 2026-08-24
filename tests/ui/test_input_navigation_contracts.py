from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtCore import Qt

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.path_discovery import discover_image_inputs

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_single_header_navigation_avoids_full_workspace_render(
    qtbot: object, monkeypatch: object
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first = ImageDocument.from_array(np.zeros((8, 8, 3), dtype=np.uint8), "fast-a.png")
    second = ImageDocument.from_array(np.ones((8, 8, 3), dtype=np.uint8), "fast-b.png")
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])
    window.set_layout_mode("Single View")

    def fail_render(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("single-header navigation rebuilt the workspace")

    monkeypatch.setattr(window, "_render_selection", fail_render)  # type: ignore[attr-defined]
    window._navigate_single_view(second.document_id)
    assert window.viewer.document is second
    window.close()


def test_direct_file_drop_replaces_selection_and_keeps_catalog_deduplicated(
    qtbot: object, tmp_path: Path
) -> None:
    paths = [tmp_path / f"drop{index}.png" for index in range(3)]
    for index, path in enumerate(paths):
        assert cv2.imwrite(str(path), np.full((30, 40), index * 10, dtype=np.uint8))
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first_inputs = discover_image_inputs(paths[:2])
    first_ids = window._register_inputs(first_inputs, resolve_raw_profiles=True)
    window._select_document_ids(first_ids)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )

    window._handle_dropped_paths([paths[2]])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.selected_documents) == 1
        and window.selected_documents[0].source is not None,
        timeout=3000,
    )
    assert len(window.documents) == 3
    assert window.selected_documents[0].source_path == paths[2].resolve()

    window.register_folders([tmp_path])
    assert len(window.documents) == 3
    assert window.document_list.document_count == 3
    assert window.document_list.topLevelItemCount() == 1
    assert window.document_list.topLevelItem(0).childCount() == 3
    assert window.document_list.topLevelItem(0).child(0).text(0) == "drop0.png"
    assert window.document_list.topLevelItem(0).child(0).text(1) == "PNG"
    assert window.selected_documents[0].source_path == paths[2].resolve()
    window.close()


def test_folder_positions_are_naturally_sorted_and_loaded_lazily(
    qtbot: object, tmp_path: Path
) -> None:
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()
    for name, value in (("image10.png", 10), ("image2.png", 2)):
        assert cv2.imwrite(str(folder_a / name), np.full((4, 4), value, dtype=np.uint8))
        assert cv2.imwrite(str(folder_b / name), np.full((4, 4), value + 1, dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.register_folders((folder_a, folder_b))
    first_ids = [
        window._document_id_by_path[window._path_key(folder / "image2.png")]
        for folder in (folder_a, folder_b)
    ]
    window._select_document_ids(first_ids)
    assert window.document_list.topLevelItemCount() == 2
    assert sorted(
        window.document_list.topLevelItem(index).childCount()
        for index in range(window.document_list.topLevelItemCount())
    ) == [2, 2]
    assert [document.display_name for document in window.selected_documents] == [
        "image2.png",
        "image2.png",
    ]
    for group_index in range(2):
        group = window.document_list.topLevelItem(group_index)
        assert group.child(0).text(0) == "image2.png"
        assert group.child(1).text(0) == "image10.png"
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )
    pending_count = sum(
        document.loading_state == "pending" for document in window.documents.values()
    )
    assert pending_count == 2

    qtbot.keyClick(window.document_list, Qt.Key.Key_PageDown)  # type: ignore[attr-defined]
    assert [document.display_name for document in window.selected_documents] == [
        "image10.png",
        "image10.png",
    ]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )
    selected_at_end = [document.document_id for document in window.selected_documents]
    window.show()
    window.activateWindow()
    window.viewer.setFocus()
    qtbot.wait(10)  # type: ignore[attr-defined]
    qtbot.keyClick(window.viewer, Qt.Key.Key_PageDown)  # type: ignore[attr-defined]
    assert [document.document_id for document in window.selected_documents] == selected_at_end
    assert "No next folder position" in window.statusBar().currentMessage()
    qtbot.keyClick(window.viewer, Qt.Key.Key_PageUp)  # type: ignore[attr-defined]
    assert [document.display_name for document in window.selected_documents] == [
        "image2.png",
        "image2.png",
    ]
    window.close()


def test_folder_position_navigation_recalculates_enabled_difference_and_keeps_focus(
    qtbot: object, tmp_path: Path
) -> None:
    folders = [tmp_path / name for name in ("reference", "candidate")]
    for folder_index, folder in enumerate(folders):
        folder.mkdir()
        for image_index in range(2):
            assert cv2.imwrite(
                str(folder / f"frame-{image_index}.png"),
                np.full((20, 24, 3), folder_index * 10 + image_index, dtype=np.uint8),
            )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.register_folders(folders)
    first_ids = [
        window._document_id_by_path[window._path_key(folder / "frame-0.png")] for folder in folders
    ]
    window._select_document_ids(first_ids)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None and window.diff_action.isChecked(),
        timeout=3000,
    )
    stale_difference = window._difference_document
    window._set_focus_document(window.selected_documents[1])
    window.next_folder_position()
    assert window._view_capacity == 2
    assert window._difference_document is stale_difference
    assert len(window.multi_compare_view.occupied_viewers) == 2
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids
        == tuple(document.document_id for document in window.selected_documents)
        and len(window.multi_compare_view.occupied_viewers) == 3,
        timeout=5000,
    )
    assert [document.display_name for document in window.selected_documents] == [
        "frame-1.png",
        "frame-1.png",
    ]
    assert window._difference_document is not None
    assert window._focus_document_id == window.selected_documents[1].document_id
    assert window.multi_compare_view.viewers[0].document is window.selected_documents[1]
    assert window.difference_panel.status.text() == "Ready"
    window.close()


def test_rapid_three_folder_navigation_coalesces_loads_under_source_byte_budget(
    qtbot: object, tmp_path: Path
) -> None:
    folders = [tmp_path / name for name in ("camera-a", "camera-b", "camera-c")]
    first_ids: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    for folder_index, folder in enumerate(folders):
        folder.mkdir()
        for image_index in range(8):
            image = np.full(
                (96, 160, 3),
                folder_index * 20 + image_index,
                dtype=np.uint8,
            )
            assert cv2.imwrite(str(folder / f"chart-{image_index:02d}.jpg"), image)
        window.register_folders([folder])
        first_ids.append(window._document_id_by_path[window._path_key(folder / "chart-00.jpg")])

    window._select_document_ids(first_ids)
    for _index in range(5):
        window.next_folder_position()
    assert [document.display_name for document in window.selected_documents] == [
        "chart-05.jpg",
        "chart-05.jpg",
        "chart-05.jpg",
    ]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._workers
        and all(document.source is not None for document in window.selected_documents),
        timeout=5000,
    )

    for _index in range(2):
        window.next_folder_position()
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: not window._workers
            and all(document.source is not None for document in window.selected_documents),
            timeout=5000,
        )
    resident = [
        document
        for document in window.documents.values()
        if document.source_path is not None and document.source is not None
    ]
    assert len(resident) > 7
    assert window.residency_manager.used_bytes == sum(
        int(document.source.nbytes) for document in resident if document.source is not None
    )
    assert window.residency_manager.used_bytes <= window.residency_manager.budget_bytes
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 3,
        timeout=3000,
    )
    window.close()


def test_direct_file_drop_replaces_active_folder_selection(qtbot: object, tmp_path: Path) -> None:
    folders = [tmp_path / name for name in ("a", "b", "c")]
    for folder_index, folder in enumerate(folders):
        folder.mkdir()
        for image_index in (1, 2):
            assert cv2.imwrite(
                str(folder / f"image{image_index}.png"),
                np.full(
                    (4, 4),
                    folder_index * 20 + image_index,
                    dtype=np.uint8,
                ),
            )

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.register_folders(folders[:2])
    initial_ids = [
        window._document_id_by_path[window._path_key(folder / "image1.png")]
        for folder in folders[:2]
    ]
    window._select_document_ids(initial_ids)

    window._handle_dropped_paths([folders[2] / "image2.png"])
    assert window.document_list.topLevelItemCount() == 3
    assert sorted(
        window.document_list.topLevelItem(index).childCount()
        for index in range(window.document_list.topLevelItemCount())
    ) == [1, 2, 2]
    assert [document.display_name for document in window.selected_documents] == ["image2.png"]
    assert window.selected_documents[0].source_path == (folders[2] / "image2.png").resolve()

    window._handle_dropped_paths([folders[0] / "image2.png"])
    assert [document.display_name for document in window.selected_documents] == ["image2.png"]
    assert window.selected_documents[0].source_path == (folders[0] / "image2.png").resolve()
    folder_key = window._folder_key(folders[0] / "image2.png")
    assert window._folder_indices[folder_key] == 1
    window.close()
