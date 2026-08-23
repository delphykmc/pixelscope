from __future__ import annotations

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
from pixelscope.io.image_reader import read_image
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_scene_inspection import (
    SceneVerificationOutcome,
    VerifiedSceneSource,
)
from pixelscope.remote.iqa_spatial import derive_spatial_scene
from pixelscope.remote.iqa_v2_domain import (
    ResultV2,
    build_measurement_context_id,
)
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_reader import load_grid_scene, load_result_v2


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


def test_shared_source_alias_selector_switches_overlay_and_block_target(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)

    base_result = _result(tmp_path)
    base_scene = base_result.scenes[0]
    grid_outcome = load_grid_scene(base_result, base_scene.scene_id)
    assert grid_outcome.status is LoadStatus.SUCCESS, grid_outcome.reason
    assert grid_outcome.data is not None

    first_source = base_scene.sources[0].source
    path = tmp_path / "shared-source.png"
    image = np.full(
        (first_source.height, first_source.width, 3),
        73,
        dtype=np.uint8,
    )
    assert cv2.imwrite(str(path), image)
    decoded = read_image(path)
    assert decoded.encoded_source_sha256 is not None
    shared_source = replace(
        first_source,
        sha256=decoded.encoded_source_sha256,
    )

    shared_measurements = tuple(
        replace(measurement, source=shared_source)
        for measurement in base_scene.sources
    )
    measurement_context_id = build_measurement_context_id(
        base_scene.scene_id,
        shared_measurements,
        base_result.attributes,
        base_scene.context_provenance,
    )
    scene = replace(
        base_scene,
        measurement_context_id=measurement_context_id,
        sources=shared_measurements,
    )
    result = replace(base_result, scenes=(scene,))
    grid_data = replace(
        grid_outcome.data,
        measurement_context_id=measurement_context_id,
        source_ids=tuple(shared_source.source_id for _ in shared_measurements),
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
    result_outcome = window.iqa_workspace.set_model(IqaExplorerModel(result))
    assert result_outcome.status is LoadStatus.SUCCESS, result_outcome.reason
    controller._populate_attribute_combo()
    window.iqa_workspace._select_scene_index(0)
    controller._sync_controls()

    controller._apply_verified_scene(result, verification)
    controller._cancel_spatial_worker()
    controller._field = derive_spatial_scene(
        result,
        scene.scene_id,
        grid_data,
        result.attributes[0].attribute_id,
    )
    controller._sync_all_overlays()

    selected = tuple(document.document_id for document in window.selected_documents)
    assert len(selected) == 1
    document_id = selected[0]
    lifecycle = window.iqa_scene_inspection_lifecycle
    aliases = lifecycle.document_variant_aliases[document_id]
    assert len(aliases) >= 2
    assert len(window.documents) == 1

    combo = controller.variant_binding_combo
    assert combo.isEnabled()
    assert combo.count() == len(aliases)
    first_variant = controller._inspected_document_variants[document_id]
    second_variant = next(
        variant_id for variant_id in aliases if variant_id != first_variant
    )

    viewer = next(
        item
        for item in controller._all_viewers()
        if item.document is not None and item.document.document_id == document_id
    )
    overlay_variants: list[str] = []
    original_set_field = inspection_module._SpatialOverlayItem.set_field

    def recording_set_field(
        item: Any,
        field_result: ResultV2,
        field: Any,
        variant_id: str,
    ) -> None:
        overlay_variants.append(variant_id)
        original_set_field(item, field_result, field, variant_id)

    monkeypatch.setattr(
        inspection_module._SpatialOverlayItem,
        "set_field",
        recording_set_field,
    )

    second_index = combo.findData(second_variant)
    assert second_index >= 0
    combo.setCurrentIndex(second_index)

    assert controller._inspected_document_variants[document_id] == second_variant
    assert overlay_variants
    assert overlay_variants[-1] == second_variant

    block_variants: list[str] = []
    monkeypatch.setattr(
        inspection_module,
        "hit_test_spatial_cell",
        lambda *_args: (0, 0),
    )
    monkeypatch.setattr(
        inspection_module,
        "spatial_cell_detail",
        lambda _result, _field, variant_id, *_cell: (
            block_variants.append(variant_id) or object()
        ),
    )
    monkeypatch.setattr(controller, "_show_block_detail", lambda _detail: None)

    scene_bounds = viewer.view_box.sceneBoundingRect()
    controller._inspect_viewer_position(viewer, scene_bounds.center())
    assert block_variants[-1] == second_variant
    window.close()
