from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QFileDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.display_gain import display_gain_state

pytestmark = pytest.mark.usefixtures("isolated_synced_qsettings")


def _profile(name: str = "sensor") -> RawProfile:
    return RawProfile(
        name=name,
        width=4,
        height=4,
        stride_bytes=8,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=10,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=64,
        white_level=1023,
    )


def _write_images(folder: Path, count: int, suffix: str = ".png") -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = [folder / f"image-{index:02d}{suffix}" for index in range(count)]
    for path in paths:
        path.write_bytes(b"fixture")
    return paths


def _disable_background_loading(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(window, "_ensure_loaded", lambda _document: None)
    monkeypatch.setattr(window, "_refresh_preload_plan", lambda: None)


def _set_open_images_result(
    monkeypatch: pytest.MonkeyPatch,
    paths: list[Path],
) -> None:
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *_args, **_kwargs: ([str(path) for path in paths], ""),
    )


def _document_id_for_path(window: MainWindow, path: Path) -> str:
    return next(
        document.document_id
        for document in window.documents.values()
        if document.source_path == path.resolve()
    )


def test_open_images_registers_and_selects_more_than_six_files(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _write_images(tmp_path / "direct", 8)
    _set_open_images_result(monkeypatch, paths)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _disable_background_loading(window, monkeypatch)

    window.open_images()

    assert len(window.documents) == 8
    assert [document.source_path for document in window.selected_documents] == [
        path.resolve() for path in paths
    ]
    assert [document.source_path for document in window.current_comparison_documents()] == [
        path.resolve() for path in paths[:6]
    ]
    assert window._view_capacity == 6
    assert window.statusBar().currentMessage() == "Opened 8 image(s)"
    window.close()


def test_open_images_mixed_ordinary_and_raw_uses_direct_file_selection_policy(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ordinary = tmp_path / "reference.png"
    ordinary.write_bytes(b"fixture")
    raw_path = tmp_path / "result.raw"
    raw_path.write_bytes(bytes(32))
    profile = _profile()
    profile.save_json(raw_path.with_suffix(".json"))
    _set_open_images_result(monkeypatch, [ordinary, raw_path])

    class UnexpectedRawDialog:
        def __init__(self, _parent: object) -> None:
            raise AssertionError("matching sidecar should resolve without a dialog")

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", UnexpectedRawDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window._dont_show_raw_json_profiles = True
    _disable_background_loading(window, monkeypatch)

    window.open_images()

    assert {document.source_path for document in window.selected_documents} == {
        ordinary.resolve(),
        raw_path.resolve(),
    }
    raw_id = _document_id_for_path(window, raw_path)
    assert window._raw_profiles[raw_id] == profile
    window.close()


@pytest.mark.parametrize("folder_count", [1, 2, 6, 20])
def test_folder_registration_has_no_viewer_capacity_limit_or_implicit_selection(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    folder_count: int,
) -> None:
    folders = [tmp_path / f"folder-{index:02d}" for index in range(folder_count)]
    for folder in folders:
        _write_images(folder, 1)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    def fail_load(_document: object) -> None:
        raise AssertionError("registration-only folder input must not start decode")

    monkeypatch.setattr(window, "_ensure_loaded", fail_load)
    result = window.register_folders([*folders, folders[0]])

    assert result.folder_count == folder_count
    assert result.image_count == folder_count
    assert len(window.documents) == folder_count
    assert window.selected_documents == []
    assert window._view_capacity == 1
    assert all(document.source is None for document in window.documents.values())
    window.close()


def test_open_folder_uses_native_single_directory_picker_and_registers_only(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "dataset"
    _write_images(folder, 2)
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(folder),
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.open_folders()

    assert len(window.documents) == 2
    assert window.selected_documents == []
    assert window.statusBar().currentMessage() == "Registered 2 image(s) from 1 folder(s)"
    window.close()


def test_folder_registration_defers_raw_profile_dialog_until_load_boundary(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "raw-folder"
    folder.mkdir()
    raw_without_sidecar = folder / "unresolved.raw"
    raw_without_sidecar.write_bytes(bytes(32))
    raw_with_sidecar = folder / "described.raw"
    raw_with_sidecar.write_bytes(bytes(32))
    profile = _profile("described")
    profile.save_json(raw_with_sidecar.with_suffix(".json"))

    class UnexpectedRawDialog:
        def __init__(self, _parent: object) -> None:
            raise AssertionError("folder registration must not prompt for RAW metadata")

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", UnexpectedRawDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    result = window.register_folders([folder])

    assert result.image_count == 2
    assert window._raw_profiles == {}
    described_id = _document_id_for_path(window, raw_with_sidecar)
    unresolved_id = _document_id_for_path(window, raw_without_sidecar)
    assert window._raw_profile_paths[described_id] == raw_with_sidecar.with_suffix(".json")
    assert unresolved_id not in window._raw_profile_paths
    assert window._preload_workers == {}
    window.close()


def test_registered_raw_sidecar_resolves_when_document_is_actually_loaded(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "raw-folder"
    folder.mkdir()
    raw_path = folder / "frame.raw"
    raw_path.write_bytes(bytes(32))
    profile = _profile()
    profile.save_json(raw_path.with_suffix(".json"))

    class UnexpectedRawDialog:
        def __init__(self, _parent: object) -> None:
            raise AssertionError("suppressed matching sidecar should not show the editor")

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", UnexpectedRawDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window._dont_show_raw_json_profiles = True
    window.register_folders([folder])
    document_id = _document_id_for_path(window, raw_path)
    document = window.documents[document_id]
    started: list[tuple[str, Path, RawProfile | None]] = []
    monkeypatch.setattr(
        window,
        "_start_load",
        lambda target_id, path, raw_profile: started.append((target_id, path, raw_profile)),
    )

    window._ensure_loaded(document)

    assert window._raw_profiles[document_id] == profile
    assert document.raw_profile == profile
    assert document.loading_state == "loading"
    assert started == [(document_id, raw_path.resolve(), profile)]
    window.close()


@pytest.mark.parametrize("folder_count", [1, 2, 6, 15])
def test_folder_drop_registers_only_and_preserves_current_selection(
    qtbot: object,
    tmp_path: Path,
    folder_count: int,
) -> None:
    current = ImageDocument.from_array(
        np.arange(16, dtype=np.uint8).reshape(4, 4),
        "current.png",
        source_path=tmp_path / "current.png",
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.add_document(current)
    folders = [tmp_path / f"dataset-{index:02d}" for index in range(folder_count)]
    for folder in folders:
        _write_images(folder, 1)
    selected_before = [document.document_id for document in window.selected_documents]
    central_before = window.central_stack.currentWidget()
    layout_before = window._layout_mode
    active_before = window._active_document_id

    window._handle_dropped_paths(folders)

    assert len(window.documents) == 1 + folder_count
    assert [document.document_id for document in window.selected_documents] == selected_before
    assert window.central_stack.currentWidget() is central_before
    assert window._layout_mode == layout_before
    assert window._active_document_id == active_before
    window.close()


@pytest.mark.parametrize("image_count", [1, 6, 8])
def test_image_drop_registers_and_selects_all_direct_files(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_count: int,
) -> None:
    paths = _write_images(tmp_path / "drop", image_count)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _disable_background_loading(window, monkeypatch)

    window._handle_dropped_paths(paths)

    assert len(window.documents) == image_count
    assert [document.source_path for document in window.selected_documents] == [
        path.resolve() for path in paths
    ]
    expected_capacity = 1 if image_count == 1 else 6
    assert window._view_capacity == expected_capacity
    window.close()


def test_mixed_drop_selects_explicit_files_but_not_folder_contents(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder_a = tmp_path / "dataset-a"
    folder_b = tmp_path / "dataset-b"
    folder_paths = [*_write_images(folder_a, 2), *_write_images(folder_b, 1)]
    direct_png = tmp_path / "reference.png"
    direct_png.write_bytes(b"fixture")
    direct_jpg = tmp_path / "result.jpg"
    direct_jpg.write_bytes(b"fixture")
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _disable_background_loading(window, monkeypatch)

    window._handle_dropped_paths([direct_png, folder_a, direct_jpg, folder_b])

    assert len(window.documents) == 5
    assert {document.source_path for document in window.selected_documents} == {
        direct_png.resolve(),
        direct_jpg.resolve(),
    }
    selected_paths = {document.source_path for document in window.selected_documents}
    assert not {path.resolve() for path in folder_paths}.intersection(selected_paths)
    window.close()


def test_registered_but_unselected_state_is_stable_and_does_not_decode(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "catalog"
    _write_images(folder, 3)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        window,
        "_start_load",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("registration must not start a source load")
        ),
    )

    window.register_folders([folder])

    assert len(window.documents) == 3
    assert window.selected_documents == []
    assert window.central_stack.currentWidget() is window.empty_workspace
    assert window.empty_workspace.title.text() == "Select an image from Files to view"
    assert not window.action_map["Fit Image"].isEnabled()
    assert not window.action_map["Export Statistics CSV..."].isEnabled()
    assert all(document.loading_state == "pending" for document in window.documents.values())
    assert all(document.source is None for document in window.documents.values())
    window.close()


def test_folder_position_uses_only_selected_folders_among_many_registered(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folders = [tmp_path / f"folder-{index:02d}" for index in range(10)]
    by_folder = [_write_images(folder, 2) for folder in folders]
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.register_folders(folders)
    _disable_background_loading(window, monkeypatch)
    selected_folder_indices = [0, 3, 7, 9]
    selected_ids = [
        _document_id_for_path(window, by_folder[index][0]) for index in selected_folder_indices
    ]
    expected_next_ids = tuple(
        _document_id_for_path(window, by_folder[index][1]) for index in selected_folder_indices
    )
    window._select_document_ids(selected_ids)

    plan = window._plan_folder_navigation(1)

    assert plan is not None
    assert plan.document_ids == expected_next_ids
    window.next_folder_position()
    assert tuple(document.document_id for document in window.selected_documents) == (
        expected_next_ids
    )
    window.close()


def test_folder_registration_preserves_active_analysis_presentation_and_runtime_state(
    qtbot: object,
    tmp_path: Path,
) -> None:
    first = ImageDocument.from_array(
        np.zeros((6, 8), dtype=np.uint8),
        "a.png",
        source_path=tmp_path / "work-a" / "a.png",
    )
    second = ImageDocument.from_array(
        np.ones((6, 8), dtype=np.uint8),
        "b.png",
        source_path=tmp_path / "work-b" / "b.png",
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])
    window.set_layout_mode("Multi View")
    window._focus_document_id = first.document_id
    window._set_active_document(first)
    window._shared_roi = RoiBounds(1, 1, 3, 3)
    window._shared_line = LineSelection(0, 0, 4, 4)
    difference = ImageDocument.from_array(
        np.ones((6, 8), dtype=np.uint8),
        "Difference",
        channel_layout="DIFFERENCE",
    )
    window._difference_document = difference
    window._difference_source_ids = (first.document_id, second.document_id)
    display_gain_state().set_gain(4.0)

    new_folders = [tmp_path / f"new-{index:02d}" for index in range(8)]
    for folder in new_folders:
        _write_images(folder, 1)

    selected_before = tuple(document.document_id for document in window.selected_documents)
    visible_before = tuple(window._visible_document_ids)
    central_before = window.central_stack.currentWidget()
    layout_before = window._layout_mode
    active_before = window._active_document_id
    focus_before = window._focus_document_id
    roi_before = window._shared_roi
    line_before = window._shared_line
    difference_before = window._difference_document
    difference_sources_before = window._difference_source_ids
    residency_before = (
        window.residency_manager.used_bytes,
        window.residency_manager.resident_count,
    )
    cache_before = (
        window.difference_panel.difference_cache.used_bytes,
        window.difference_panel.difference_cache.entry_count,
    )

    window.register_folders(new_folders)

    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert tuple(window._visible_document_ids) == visible_before
    assert window.central_stack.currentWidget() is central_before
    assert window._layout_mode == layout_before
    assert window._active_document_id == active_before
    assert window._focus_document_id == focus_before
    assert window._shared_roi == roi_before
    assert window._shared_line == line_before
    assert window._difference_document is difference_before
    assert window._difference_source_ids == difference_sources_before
    assert display_gain_state().gain == 4.0
    assert (
        window.residency_manager.used_bytes,
        window.residency_manager.resident_count,
    ) == residency_before
    assert (
        window.difference_panel.difference_cache.used_bytes,
        window.difference_panel.difference_cache.entry_count,
    ) == cache_before
    window.close()
