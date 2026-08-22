from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_scene_inspection import (
    SceneVerificationOutcome,
    VerifiedSceneSource,
)
from pixelscope.remote.iqa_v2_domain import ResultV2
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_reader import load_result_v2


def _result(tmp_path: Path) -> ResultV2:
    root = write_golden_result_v2(tmp_path / "result")
    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    return outcome.result


def _document(tmp_path: Path, index: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((8, 12, 3), index, dtype=np.uint8),
        f"local-{index}.png",
        source_path=tmp_path / f"local-{index}.png",
    )


def test_pending_inspect_callback_cannot_overwrite_newer_selected_intent(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QSettings().clear()

    window = MainWindow()
    qtbot.addWidget(window)
    local = [_document(tmp_path, index) for index in range(2)]
    for document in local:
        window.add_document(document, select=False)
    window._select_document_ids([local[0].document_id])
    _compose_main_window_presentation(window)

    result = _result(tmp_path)
    outcome = window.iqa_workspace.set_model(IqaExplorerModel(result))
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    window.iqa_workspace._select_scene_index(0)

    controller = window.iqa_scene_inspection_controller
    scene = result.scenes[0]
    generation = 17
    controller._inspect_generation = generation
    controller._inspect_result_identity = (result.result_id, id(result))
    controller._inspect_local_intent_generation = controller._local_intent_generation
    verification = SceneVerificationOutcome(
        scene_id=scene.scene_id,
        sources=tuple(
            VerifiedSceneSource(
                measurement.variant_id,
                measurement.source,
                tmp_path / f"verified-{index}.png",
            )
            for index, measurement in enumerate(scene.sources)
        ),
    )

    window._select_document_ids([local[1].document_id])
    assert controller._local_intent_generation != controller._inspect_local_intent_generation

    controller._verification_succeeded("task", None, generation, verification)

    assert [document.document_id for document in window.selected_documents] == [
        local[1].document_id
    ]
    assert controller.inspected_scene_id is None
    assert not controller.return_valid
    window.close()
