from __future__ import annotations

import struct
from pathlib import Path
from threading import Event
from typing import Any

import numpy as np
import pytest
from PySide6.QtCore import QSettings

import pixelscope.ui.iqa_preview_lifecycle as preview_lifecycle_module
import pixelscope.ui.iqa_submission as iqa_submission_module
from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.remote.iqa_submission import (
    FolderPairEntry,
    ImageProbe,
    pair_folders,
)
from pixelscope.ui.iqa_preview_lifecycle import RemoteIqaPreviewLifecycle
from pixelscope.ui.iqa_submission import _FolderPreviewPayload


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QSettings().clear()


def _documents(tmp_path: Path, count: int = 2) -> list[ImageDocument]:
    documents: list[ImageDocument] = []
    for index in range(count):
        path = tmp_path / f"page-{index}.png"
        documents.append(
            ImageDocument.from_array(
                np.full((12, 18, 3), index * 20, dtype=np.uint8),
                path.name,
                source_path=path,
            )
        )
    return documents


def _write_probe_bmp(path: Path, width: int = 8, height: int = 6) -> None:
    path.write_bytes(b"BM" + (b"\x00" * 12) + struct.pack("<Iii", 40, width, height))


def _authority_snapshot(window: MainWindow) -> tuple[object, ...]:
    return (
        tuple(window.documents),
        tuple(document.document_id for document in window.selected_documents),
        tuple(document.document_id for document in window.current_comparison_documents()),
        window._active_document_id,
        window._focus_document_id,
        window.residency_manager.resident_document_ids,
        window.residency_manager.used_bytes,
        window.preload_controller.generation,
        window.preload_controller.current_plan,
        window.preload_controller.diagnostics,
        tuple(window._preload_workers),
        tuple(window._preload_worker_requests),
        tuple(window._promoted_preload_tokens.items()),
    )


def test_folder_preview_edit_during_validation_recovers_validate_action(
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    workspace = window.remote_iqa_workspace
    guard = window.remote_iqa_preview_lifecycle
    assert isinstance(guard, RemoteIqaPreviewLifecycle)

    started = Event()
    release = Event()
    calls = 0

    def fake_pair_folders(folder_a: str, folder_b: str) -> tuple[FolderPairEntry, ...]:
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            if not release.wait(5):
                raise RuntimeError("test preview release timed out")
        return (
            FolderPairEntry(
                "scene_000000",
                ImageProbe(Path(folder_a) / "a.bmp", 8, 6),
                ImageProbe(Path(folder_b) / "b.bmp", 8, 6),
            ),
        )

    monkeypatch.setattr(preview_lifecycle_module, "pair_folders", fake_pair_folders)
    workspace.folder_a.setText("folder-a-old")
    workspace.folder_b.setText("folder-b")
    workspace.preview_button.click()
    qtbot.waitUntil(started.is_set, timeout=2000)
    assert not workspace.preview_button.isEnabled()

    workspace.folder_a.setText("folder-a-new")
    assert workspace.preview_identity is None
    assert not workspace.preview_button.isEnabled()

    release.set()
    qtbot.waitUntil(workspace.preview_button.isEnabled, timeout=3000)
    assert workspace.preview_identity is None

    workspace.preview_button.click()
    qtbot.waitUntil(
        lambda: workspace.preview_identity == ("folder-a-new", "folder-b"),
        timeout=3000,
    )
    assert calls == 2
    assert workspace.preview_button.isEnabled()
    window.close()


def test_current_pair_submission_keeps_page_order_after_primary_and_active_reorder(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    documents = _documents(tmp_path)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    _compose_main_window_presentation(window)
    controller = window.remote_iqa_controller

    window._set_focus_document(documents[1])
    window._set_active_document(documents[1])
    assert window.multi_compare_view.viewers[0].document is documents[1]
    assert window.current_comparison_documents() == documents

    captured_paths: list[tuple[Path, Path]] = []

    def capture_pair(path_a: Path, path_b: Path) -> tuple[FolderPairEntry, ...]:
        captured_paths.append((Path(path_a), Path(path_b)))
        return ()

    def capture_start(
        _submission_kind: str,
        entries_factory: Any,
        _settings: object,
    ) -> None:
        entries_factory()

    monkeypatch.setattr(iqa_submission_module, "pair_current_paths", capture_pair)
    monkeypatch.setattr(controller, "_start_submission", capture_start)

    controller.submit_current_pair()

    assert captured_paths == [(documents[0].source_path, documents[1].source_path)]
    assert window.current_comparison_documents() == documents
    window.close()


def test_folder_pair_preparation_does_not_mutate_local_image_authorities(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    documents = _documents(tmp_path, 3)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents[:2]])
    window.set_layout_mode("Multi View")
    _compose_main_window_presentation(window)
    controller = window.remote_iqa_controller
    workspace = window.remote_iqa_workspace

    folder_a = tmp_path / "folder-a"
    folder_b = tmp_path / "folder-b"
    folder_a.mkdir()
    folder_b.mkdir()
    _write_probe_bmp(folder_a / "scene.bmp")
    _write_probe_bmp(folder_b / "scene.bmp")

    before = _authority_snapshot(window)
    preview = pair_folders(folder_a, folder_b)
    workspace.folder_a.setText(str(folder_a))
    workspace.folder_b.setText(str(folder_b))
    workspace.set_folder_preview(_FolderPreviewPayload(str(folder_a), str(folder_b), preview))
    assert _authority_snapshot(window) == before

    prepared: list[FolderPairEntry] = []

    def capture_start(
        submission_kind: str,
        entries_factory: Any,
        _settings: object,
    ) -> None:
        assert submission_kind == "folder_pair"
        prepared.extend(entries_factory())

    monkeypatch.setattr(controller, "_start_submission", capture_start)
    controller.submit_folders(str(folder_a), str(folder_b))

    assert len(prepared) == 1
    assert prepared[0].source_a.path == folder_a / "scene.bmp"
    assert prepared[0].source_b.path == folder_b / "scene.bmp"
    assert _authority_snapshot(window) == before
    window.close()
