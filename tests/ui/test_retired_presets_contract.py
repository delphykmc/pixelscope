"""Retired W05/W06 presets have no hidden UI or duplicate state authority."""

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    return window


def test_no_hidden_w05_or_w06_selector_or_duplicate_state_owner(qtbot: object) -> None:
    window = _window(qtbot)
    assert window.findChild(QWidget, "workspacePresetControl") is None
    assert window.findChild(QWidget, "comparisonPresetControl") is None
    assert not hasattr(window.beta_workspace_hardening_controller, "workspace_presets")
    assert not hasattr(window.quick_compare_controller, "comparison_presets")
    assert window.action_map["Open Images..."] in window._menu_map["File"].actions()
    assert window.action_map["Reset Workspace Layout"] in window._menu_map["View"].actions()
    window.close()


@pytest.mark.parametrize("count", [2, 4, 6, 8])
def test_canonical_current_page_survives_removal(qtbot: object, tmp_path: Path, count: int) -> None:
    window = _window(qtbot)
    documents = [
        ImageDocument.from_array(
            np.full((48, 64), 20 + index, dtype=np.uint8),
            "same.png",
            source_path=tmp_path / str(index) / "same.png",
        )
        for index in range(count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    assert tuple(d.document_id for d in window.selected_documents) == tuple(
        d.document_id for d in documents
    )
    assert tuple(d.document_id for d in window.current_comparison_documents()) == tuple(
        d.document_id for d in documents[:6]
    )
    if count > 6:
        window.next_comparison_page()
        assert tuple(d.document_id for d in window.current_comparison_documents()) == tuple(
            d.document_id for d in documents[6:]
        )
    assert window._difference_document is None
    window.close()


def test_retired_qsettings_are_not_reintroduced(qtbot: object) -> None:
    window = _window(qtbot)
    assert window.settings.value("ui/workspace_preset") is None
    assert window.settings.value("ui/workspace_layouts/v1/Compare/main_state") is None
    window.action_map["Reset Workspace Layout"].trigger()
    assert window.settings.value("ui/workspace_preset") is None
    window.close()
