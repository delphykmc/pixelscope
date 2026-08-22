from __future__ import annotations

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
from pixelscope.io.path_discovery import ImageInput
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_scene_inspection import (
    SceneVerificationOutcome,
    VerifiedSceneSource,
)
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


def _local_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((12, 18, 3), index * 10, dtype=np.uint8),
            f"local-{index}.png",
            source_path=tmp_path / f"local-{index}.png",
        )
        for index in range(count)
    ]


def _result(tmp_path: Path) -> ResultV2:
    root = write_golden_result_v2(tmp_path / "result")
    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    return outcome.result


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
                (scene_index * 31 + variant_index * 47) % 255,
                dtype=np.uint8,
            )
            assert cv2.imwrite(str(path), image)
            scene_paths.append(path)
        paths[scene.scene_id] = tuple(scene_paths)
    return paths


def _present_result(window: MainWindow, result: ResultV2, scene_index: int = 0) -> None:
    outcome = window.iqa_workspace.set_model(IqaExplorerModel(result))
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    controller = window.iqa_scene_inspection_controller
    controller._populate_attribute_combo()
    window.iqa_workspace._select_scene_index(scene_index)
    controller._sync_controls()


def _install_fake_verifier(
    monkeypatch: pytest.MonkeyPatch,
    paths: dict[str, tuple[Path, ...]],
) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(
        inspection_module,
        "inspect_unavailable_reason",
        lambda _result, _scene_id, _settings: None,
    )

    def verify(result: ResultV2, scene_id: str, _settings: object) -> SceneVerificationOutcome:
        calls.append(scene_id)
        scene = result.scene(scene_id)
        return SceneVerificationOutcome(
            scene_id=scene_id,
            sources=tuple(
                VerifiedSceneSource(measurement.variant_id, measurement.source, path)
                for measurement, path in zip(scene.sources, paths[scene_id], strict=True)
            ),
        )

    monkeypatch.setattr(inspection_module, "verify_scene_sources", verify)
    return calls


def test_result_browsing_is_passive_and_active_picks_guard_explicit_inspect(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    documents = _local_documents(tmp_path, 2)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    paths = _native_paths(tmp_path, result)
    calls = _install_fake_verifier(monkeypatch, paths)
    selected_before = tuple(document.document_id for document in window.selected_documents)
    registered_before = tuple(window.documents)
    _present_result(window, result)

    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert tuple(window.documents) == registered_before

    review = window.review_selection_controller
    assert review.enter_review()
    window.iqa_scene_inspection_controller.inspect_selected_scene()
    qtbot.wait(20)
    assert calls == []
    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert "temporary Picks" in window.iqa_scene_inspection_controller.inspect_status.text()
    review.cancel_review()
    window.close()


def test_inspect_reuses_registered_source_and_return_restores_single_view_page_and_active(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    local = _local_documents(tmp_path, 8)
    for document in local:
        window.add_document(document, select=False)
    _compose_main_window_presentation(window)
    window._select_document_ids([document.document_id for document in local])
    window.set_layout_mode("Single View")
    window._show_single_document(local[7], 7)
    assert [item.document_id for item in window.current_comparison_documents()] == [
        local[6].document_id,
        local[7].document_id,
    ]
    assert window.viewer.document is local[7]

    result = _result(tmp_path)
    paths = _native_paths(tmp_path, result)
    _install_fake_verifier(monkeypatch, paths)
    first_registered = window._register_inputs(
        (ImageInput(paths[result.scenes[0].scene_id][0]),),
        resolve_raw_profiles=False,
    )[0]
    registered_before_inspect = len(window.documents)
    _present_result(window, result)

    controller = window.iqa_scene_inspection_controller
    controller.inspect_selected_scene()
    qtbot.waitUntil(lambda: controller.inspected_scene_id == result.scenes[0].scene_id, timeout=3000)
    inspected_ids = [document.document_id for document in window.selected_documents]
    assert len(inspected_ids) == len(result.scenes[0].sources)
    assert first_registered in inspected_ids
    assert len(window.documents) == registered_before_inspect + len(result.scenes[0].sources) - 1
    assert controller.return_valid

    controller.return_to_local_workspace()

    assert [document.document_id for document in window.selected_documents] == [
        document.document_id for document in local
    ]
    assert [document.document_id for document in window.current_comparison_documents()] == [
        local[6].document_id,
        local[7].document_id,
    ]
    assert window._layout_mode == "Single View"
    assert window._active_document_id == local[7].document_id
    assert window.viewer.document is local[7]
    assert not controller.return_valid
    window.close()


def test_failed_source_verification_preserves_registered_selected_and_presentation(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    local = _local_documents(tmp_path, 2)
    for document in local:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in local])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    monkeypatch.setattr(
        inspection_module,
        "inspect_unavailable_reason",
        lambda _result, _scene_id, _settings: None,
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_scene_sources",
        lambda _result, scene_id, _settings: SceneVerificationOutcome(
            scene_id=scene_id,
            reason="Source hash changed",
            failed_source_id="source-x",
        ),
    )
    _present_result(window, result)
    controller = window.iqa_scene_inspection_controller
    before_registered = tuple(window.documents)
    before_selected = tuple(document.document_id for document in window.selected_documents)
    before_widget = window.central_stack.currentWidget()

    controller.inspect_selected_scene()
    qtbot.waitUntil(lambda: "Source hash changed" in controller.inspect_status.text(), timeout=3000)

    assert tuple(window.documents) == before_registered
    assert tuple(document.document_id for document in window.selected_documents) == before_selected
    assert window.central_stack.currentWidget() is before_widget
    assert not controller.return_valid
    window.close()


def test_newer_local_selection_invalidates_return_instead_of_overwriting_user_intent(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    local = _local_documents(tmp_path, 3)
    for document in local:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in local[:2]])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    paths = _native_paths(tmp_path, result)
    _install_fake_verifier(monkeypatch, paths)
    _present_result(window, result)
    controller = window.iqa_scene_inspection_controller
    controller.inspect_selected_scene()
    qtbot.waitUntil(lambda: controller.inspected_scene_id == result.scenes[0].scene_id, timeout=3000)
    assert controller.return_valid

    window._select_document_ids([local[2].document_id])
    assert not controller.return_valid
    assert [document.document_id for document in window.selected_documents] == [local[2].document_id]

    controller.return_to_local_workspace()
    assert [document.document_id for document in window.selected_documents] == [local[2].document_id]
    assert "Return is unavailable" in controller.inspect_status.text()
    window.close()


def test_iqa_reference_and_local_primary_remain_independent(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    local = _local_documents(tmp_path, 2)
    for document in local:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in local])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    paths = _native_paths(tmp_path, result)
    _install_fake_verifier(monkeypatch, paths)
    _present_result(window, result)
    controller = window.iqa_scene_inspection_controller
    controller.inspect_selected_scene()
    qtbot.waitUntil(lambda: controller.inspected_scene_id == result.scenes[0].scene_id, timeout=3000)

    reference_before = window.iqa_workspace.reference_variant_id
    page = window.current_comparison_documents()
    assert len(page) >= 2
    window._set_focus_document(page[1])

    assert window.iqa_workspace.reference_variant_id == reference_before
    assert window._focus_document_id == page[1].document_id
    window.close()
