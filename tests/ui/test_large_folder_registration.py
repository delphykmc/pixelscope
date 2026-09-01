from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QFileDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.app.registration_controller import install_large_folder_registration
from pixelscope.io import path_discovery
from pixelscope.io.path_discovery import RegistrationDiscovery, discover_registration_inputs
from pixelscope.ui.document_list import DocumentListWidget

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _wait_idle(qtbot: object, controller: object) -> None:
    qtbot.waitUntil(lambda: controller.is_idle, timeout=5000)  # type: ignore[attr-defined]


def test_document_tree_bulk_insert_uses_one_natural_key_per_item(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tree = DocumentListWidget()
    qtbot.addWidget(tree)  # type: ignore[attr-defined]
    original = path_discovery.natural_sort_key
    calls = 0

    def counting_key(path: Path) -> tuple[object, ...]:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr("pixelscope.ui.document_list.natural_sort_key", counting_key)
    with tree.bulk_update():
        for index in range(100, 0, -1):
            path = tmp_path / f"image{index}.png"
            tree.add_document_item(str(index), path.name, path)

    assert calls == 100
    group = tree.topLevelItem(0)
    assert [group.child(index).text(0) for index in range(group.childCount())] == [
        f"image{index}.png" for index in range(1, 101)
    ]
    assert tree.updatesEnabled()


def test_large_folder_registration_is_chunked_ordered_deduplicated_and_lazy(
    qtbot: object, tmp_path: Path
) -> None:
    folder = tmp_path / "large"
    folder.mkdir()
    for index in range(1, 131):
        (folder / f"image{index}.png").write_bytes(b"not-decoded")

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window, chunk_size=16)
    events: list[tuple[str, int, int | None]] = []
    controller.progress_changed.connect(
        lambda phase, completed, total: events.append((phase, completed, total))
    )

    controller.enqueue((folder, folder))
    assert controller.progress.phase == "scanning"
    assert controller.progress.total is None
    _wait_idle(qtbot, controller)

    assert len(window.documents) == 130
    assert window.document_list.document_count == 130
    assert window.document_list.topLevelItemCount() == 1
    group = window.document_list.topLevelItem(0)
    assert [group.child(index).text(0) for index in range(group.childCount())] == [
        f"image{index}.png" for index in range(1, 131)
    ]
    folder_key = window._folder_key(folder / "image1.png")
    folder_names = [
        window.documents[document_id].display_name
        for document_id in window._folder_documents[folder_key]
    ]
    assert folder_names == [f"image{index}.png" for index in range(1, 131)]
    assert not window.selected_documents
    assert all(document.source is None for document in window.documents.values())
    assert all(
        document.loading_state == "pending" for document in window.documents.values()
    )
    assert not window._workers
    assert not window._preload_workers

    registering = [
        (completed, total)
        for phase, completed, total in events
        if phase == "registering"
    ]
    assert registering[0] == (0, 130)
    assert registering[-1] == (130, 130)
    completed_values = [completed for completed, _total in registering]
    assert completed_values == sorted(completed_values)
    assert all(
        0 < current - previous <= 16
        for previous, current in zip(completed_values, completed_values[1:], strict=False)
        if current != previous
    )
    assert events[-1] == ("idle", 0, None)

    controller.enqueue((folder,))
    _wait_idle(qtbot, controller)
    assert len(window.documents) == 130
    assert window.document_list.document_count == 130
    window.close()


def test_registration_worker_is_filesystem_only_and_gui_mutation_stays_on_gui_thread(
    qtbot: object, tmp_path: Path
) -> None:
    folder = tmp_path / "thread-boundary"
    folder.mkdir()
    for index in range(4):
        (folder / f"image{index}.png").write_bytes(b"x")

    discovery_threads: list[int] = []

    def observed_discovery(paths: object, **kwargs: object) -> RegistrationDiscovery:
        discovery_threads.append(threading.get_ident())
        return discover_registration_inputs(paths, **kwargs)  # type: ignore[arg-type]

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(
        window,
        discovery_function=observed_discovery,
        chunk_size=2,
    )
    gui_thread = threading.get_ident()
    registration_threads: list[int] = []
    original_register_input = window._register_input

    def observed_register_input(*args: object, **kwargs: object) -> str | None:
        registration_threads.append(threading.get_ident())
        return original_register_input(*args, **kwargs)

    window._register_input = observed_register_input
    controller.enqueue((folder,))
    _wait_idle(qtbot, controller)

    assert discovery_threads and discovery_threads[0] != gui_thread
    assert registration_threads == [gui_thread] * 4
    window.close()


def test_open_folder_and_mixed_drop_share_async_registration_contract(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    open_folder = tmp_path / "open-folder"
    drop_folder = tmp_path / "drop-folder"
    open_folder.mkdir()
    drop_folder.mkdir()
    for index in range(2):
        (open_folder / f"open{index}.png").write_bytes(b"x")
        (drop_folder / f"drop{index}.png").write_bytes(b"x")
    direct = tmp_path / "direct.png"
    assert cv2.imwrite(str(direct), np.full((8, 8), 25, dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window, chunk_size=2)
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(open_folder),
    )

    controller.open_folders()
    _wait_idle(qtbot, controller)
    assert len(window.documents) == 2
    assert not window.selected_documents

    controller.handle_dropped_paths([drop_folder, direct])
    _wait_idle(qtbot, controller)
    assert len(window.documents) == 5
    assert [document.source_path for document in window.selected_documents] == [direct.resolve()]
    assert all(
        document.source is None
        for document in window.documents.values()
        if document.source_path is not None and document.source_path.parent == drop_folder.resolve()
    )
    window.close()


def test_registration_cancel_rejects_stale_discovery_result(
    qtbot: object, tmp_path: Path
) -> None:
    started = threading.Event()

    def blocking_discovery(_paths: object, *, checkpoint: object) -> RegistrationDiscovery:
        started.set()
        while True:
            checkpoint()  # type: ignore[operator]

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(
        window,
        discovery_function=blocking_discovery,
    )
    controller.enqueue((tmp_path,))
    qtbot.waitUntil(started.is_set, timeout=3000)  # type: ignore[attr-defined]
    task_id = controller._discovery_task_id
    generation = controller._active_generation
    assert task_id is not None and generation is not None

    controller.cancel_active()
    controller._discovery_succeeded(
        task_id,
        None,
        generation,
        RegistrationDiscovery((), 1, 1, ()),
    )
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller.pool.activeThreadCount() == 0, timeout=3000
    )

    assert controller.stale_result_count == 1
    assert controller.progress.phase == "idle"
    assert not window.documents
    window.close()


def test_application_close_cancels_registration_without_late_catalog_mutation(
    qtbot: object, tmp_path: Path
) -> None:
    started = threading.Event()

    def blocking_discovery(_paths: object, *, checkpoint: object) -> RegistrationDiscovery:
        started.set()
        while True:
            checkpoint()  # type: ignore[operator]

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(
        window,
        discovery_function=blocking_discovery,
    )
    controller.enqueue((tmp_path,))
    qtbot.waitUntil(started.is_set, timeout=3000)  # type: ignore[attr-defined]

    window.close()

    assert controller.pool.activeThreadCount() == 0
    assert controller.progress.phase == "idle"
    assert not window.documents