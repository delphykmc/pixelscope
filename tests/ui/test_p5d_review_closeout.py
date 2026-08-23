from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QSettings

import pixelscope.ui.iqa_scene_inspection as inspection_module
from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.image_reader import read_image
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_scene_inspection import (
    SceneVerificationOutcome,
    VerifiedSceneSource,
)
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_v2_domain import ResultV2
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_reader import load_result_v2


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QSettings().clear()


def _result(tmp_path: Path) -> ResultV2:
    root = write_golden_result_v2(tmp_path / "result")
    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    return outcome.result


def _local_document(tmp_path: Path, index: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((10, 14, 3), 17 + index, dtype=np.uint8),
        f"local-{index}.png",
        source_path=tmp_path / f"local-{index}.png",
    )


def _native_paths(tmp_path: Path, result: ResultV2) -> dict[str, tuple[Path, ...]]:
    paths: dict[str, tuple[Path, ...]] = {}
    for scene_index, scene in enumerate(result.scenes):
        scene_paths: list[Path] = []
        for variant_index, measurement in enumerate(scene.sources):
            source = measurement.source
            path = tmp_path / "native" / scene.scene_id / f"{variant_index}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image = np.full(
                (source.height, source.width, 3),
                (scene_index * 43 + variant_index * 61 + 29) % 255,
                dtype=np.uint8,
            )
            assert cv2.imwrite(str(path), image)
            scene_paths.append(path)
        paths[scene.scene_id] = tuple(scene_paths)
    return paths


def _verified_outcome(
    result: ResultV2,
    scene_id: str,
    paths: dict[str, tuple[Path, ...]],
) -> SceneVerificationOutcome:
    scene = result.scene(scene_id)
    verified: list[VerifiedSceneSource] = []
    for measurement, path in zip(scene.sources, paths[scene_id], strict=True):
        decoded = read_image(path)
        assert decoded.encoded_source_sha256 is not None
        verified.append(
            VerifiedSceneSource(
                measurement.variant_id,
                replace(measurement.source, sha256=decoded.encoded_source_sha256),
                path,
                decoded,
            )
        )
    return SceneVerificationOutcome(scene_id=scene_id, sources=tuple(verified))


def _install_fake_verifier(
    monkeypatch: pytest.MonkeyPatch,
    result: ResultV2,
    paths: dict[str, tuple[Path, ...]],
) -> None:
    monkeypatch.setattr(
        inspection_module,
        "inspect_unavailable_reason",
        lambda _result, _scene_id, _settings: None,
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_scene_sources",
        lambda _result, scene_id, _settings: _verified_outcome(result, scene_id, paths),
    )


def _present_result(window: MainWindow, result: ResultV2) -> None:
    outcome = window.iqa_workspace.set_model(IqaExplorerModel(result))
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    window.iqa_scene_inspection_controller._populate_attribute_combo()
    window.iqa_workspace._select_scene_index(0)
    window.iqa_scene_inspection_controller._sync_controls()


def test_inspect_replaces_stale_resident_pixels_with_verified_decoded_generation(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    local = _local_document(tmp_path, 0)
    window.add_document(local, select=False)
    window._select_document_ids([local.document_id])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    paths = _native_paths(tmp_path, result)
    scene_id = result.scenes[0].scene_id
    reused_path = paths[scene_id][0]
    verified_bytes = reused_path.read_bytes()

    old_pixels = np.full(
        (result.scenes[0].sources[0].source.height, result.scenes[0].sources[0].source.width, 3),
        3,
        dtype=np.uint8,
    )
    assert cv2.imwrite(str(reused_path), old_pixels)
    resident = read_image(reused_path)
    window.add_document(resident, select=False)
    resident_id = resident.document_id
    old_sha = resident.encoded_source_sha256
    old_generation = resident.generation
    old_source = np.asarray(resident.source).copy()

    reused_path.write_bytes(verified_bytes)
    _install_fake_verifier(monkeypatch, result, paths)
    _present_result(window, result)

    controller = window.iqa_scene_inspection_controller
    controller.inspect_selected_scene()
    qtbot.waitUntil(lambda: controller.inspected_scene_id == scene_id, timeout=3000)

    committed = window.documents[resident_id]
    assert resident_id in [document.document_id for document in window.selected_documents]
    assert committed.encoded_source_sha256 is not None
    assert committed.encoded_source_sha256 != old_sha
    assert committed.generation == old_generation + 1
    assert not np.array_equal(np.asarray(committed.source), old_source)
    window.close()


def test_same_source_variant_bindings_use_one_canonical_files_document(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    local = _local_document(tmp_path, 0)
    window.add_document(local, select=False)
    window._select_document_ids([local.document_id])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    paths = _native_paths(tmp_path, result)
    _present_result(window, result)
    scene = result.scenes[0]
    path = paths[scene.scene_id][0]
    decoded = read_image(path)
    assert decoded.encoded_source_sha256 is not None
    shared_source = replace(
        scene.sources[0].source,
        sha256=decoded.encoded_source_sha256,
    )
    verification = SceneVerificationOutcome(
        scene_id=scene.scene_id,
        sources=tuple(
            VerifiedSceneSource(
                measurement.variant_id,
                shared_source,
                path,
                decoded,
            )
            for measurement in scene.sources
        ),
    )

    controller = window.iqa_scene_inspection_controller
    controller._apply_verified_scene(result, verification)

    selected = [document.document_id for document in window.selected_documents]
    assert len(selected) == 1
    aliases = window.iqa_scene_inspection_lifecycle.document_variant_aliases
    assert aliases[selected[0]] == tuple(item.variant_id for item in scene.sources)
    assert "variant binding" in controller.inspect_status.text()
    window.close()


def test_post_inspect_pick_invalidates_return_without_clearing_pick_state(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    local = _local_document(tmp_path, 0)
    window.add_document(local, select=False)
    window._select_document_ids([local.document_id])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    paths = _native_paths(tmp_path, result)
    _install_fake_verifier(monkeypatch, result, paths)
    _present_result(window, result)
    controller = window.iqa_scene_inspection_controller
    controller.inspect_selected_scene()
    qtbot.waitUntil(
        lambda: controller.inspected_scene_id == result.scenes[0].scene_id,
        timeout=3000,
    )
    assert controller.return_valid

    viewer = next(
        item
        for item in window.multi_compare_view.viewers
        if item.presented_document is not None
    )
    picked_id = viewer.presented_document.document_id
    viewer.header.pick_requested.emit(True)
    qtbot.waitUntil(lambda: window.review_selection_controller.active, timeout=1000)

    selected_after_pick = tuple(
        document.document_id for document in window.selected_documents
    )
    assert not controller.return_valid
    assert picked_id in window.review_selection_controller.picked_ids

    controller.return_to_local_workspace()

    assert window.review_selection_controller.active
    assert picked_id in window.review_selection_controller.picked_ids
    assert (
        tuple(document.document_id for document in window.selected_documents)
        == selected_after_pick
    )
    window.close()


def test_storage_mapping_change_cancels_pending_verification_and_drops_callback(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    local = _local_document(tmp_path, 0)
    window.add_document(local, select=False)
    window._select_document_ids([local.document_id])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    paths = _native_paths(tmp_path, result)
    started = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(
        inspection_module,
        "inspect_unavailable_reason",
        lambda _result, _scene_id, _settings: None,
    )

    def delayed_verify(
        _result: ResultV2,
        scene_id: str,
        _settings: object,
    ) -> SceneVerificationOutcome:
        started.set()
        release.wait(timeout=2.0)
        return _verified_outcome(result, scene_id, paths)

    monkeypatch.setattr(inspection_module, "verify_scene_sources", delayed_verify)
    _present_result(window, result)
    controller = window.iqa_scene_inspection_controller
    selected_before = tuple(document.document_id for document in window.selected_documents)

    controller.inspect_selected_scene()
    qtbot.waitUntil(started.is_set, timeout=1000)
    revision_before = window.iqa_scene_inspection_lifecycle.settings_revision
    window.remote_iqa_controller.settings_changed()
    assert window.iqa_scene_inspection_lifecycle.settings_revision == revision_before + 1
    release.set()
    qtbot.wait(100)

    assert controller.inspected_scene_id is None
    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert not controller.return_valid
    window.close()


def test_storage_mapping_change_refreshes_inspect_availability(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    result = _result(tmp_path)

    monkeypatch.setattr(
        inspection_module,
        "inspect_unavailable_reason",
        lambda _result, _scene_id, settings: (
            None if settings.root("shared") is not None else "Source root is not configured"
        ),
    )
    _present_result(window, result)
    controller = window.iqa_scene_inspection_controller
    assert not controller.inspect_button.isEnabled()

    window.application_settings = replace(
        window.application_settings,
        remote_iqa=RemoteIqaSettings(
            storage_roots=(RemoteIqaStorageRoot("shared", r"C:\iqa"),),
        ),
    )
    window.remote_iqa_controller.settings_changed()
    assert controller.inspect_button.isEnabled()

    window.application_settings = replace(
        window.application_settings,
        remote_iqa=RemoteIqaSettings(),
    )
    window.remote_iqa_controller.settings_changed()
    assert not controller.inspect_button.isEnabled()
    window.close()
