from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.tile_header import TileHeader
from pixelscope.ui.toolbar_icons import toolbar_icon


@pytest.mark.parametrize(
    "kind",
    (
        "fit",
        "actual_size",
        "zoom_in",
        "zoom_out",
        "sync",
        "difference",
        "plots",
        "export",
        "pin",
    ),
)
def test_toolbar_icon_factory_has_explicit_interaction_states(kind: str) -> None:
    icon = toolbar_icon(kind)
    size = QSize(16, 16)
    normal = icon.pixmap(size, QIcon.Mode.Normal, QIcon.State.Off)
    checked = icon.pixmap(size, QIcon.Mode.Normal, QIcon.State.On)
    disabled = icon.pixmap(size, QIcon.Mode.Disabled, QIcon.State.Off)

    assert not icon.isNull()
    assert not normal.isNull()
    assert normal.cacheKey() != checked.cacheKey()
    assert normal.cacheKey() != disabled.cacheKey()
    assert toolbar_icon(kind).cacheKey() == icon.cacheKey()


def test_toolbar_icon_factory_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unsupported toolbar icon"):
        toolbar_icon("unknown")


def test_focus_pin_uses_checked_state_instead_of_platform_pixmaps(qtbot: object) -> None:
    header = TileHeader()
    qtbot.addWidget(header)  # type: ignore[attr-defined]
    header.set_focus_control_visible(True)

    assert header.focus.objectName() == "focusPin"
    assert header.focus.isCheckable()
    assert not header.focus.icon().isNull()

    header.set_focus(False)
    assert not header.focus.isChecked()
    assert header.focus.toolTip() == "Pin as focus tile"

    header.set_focus(True)
    assert header.focus.isChecked()
    assert header.focus.toolTip() == "Focus tile is pinned"


def test_main_toolbar_uses_distinct_internal_icons_and_compact_labels(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    actions = {
        "Fit Image": (window.action_map["Fit Image"], "Fit"),
        "100% Zoom": (window.action_map["100% Zoom"], "1:1"),
        "Zoom In": (window.zoom_in_action, "Zoom +"),
        "Zoom Out": (window.zoom_out_action, "Zoom −"),
        "Sync View": (window.sync_action, "Sync"),
        "Diff": (window.diff_action, "Diff"),
        "Plots": (window.plots_action, "Plots"),
        "Export": (window.export_toolbar_action, "Export"),
    }

    icon_keys: set[int] = set()
    for action, icon_text in actions.values():
        assert not action.icon().isNull()
        assert action.iconText() == icon_text
        icon_keys.add(action.icon().cacheKey())
    assert len(icon_keys) == len(actions)
    assert window.main_toolbar.accessibleName() == "PixelScope main toolbar"


def test_toolbar_enablement_and_tooltips_follow_workspace_state(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert not window.action_map["Fit Image"].isEnabled()
    assert not window.action_map["100% Zoom"].isEnabled()
    assert not window.zoom_in_action.isEnabled()
    assert not window.zoom_out_action.isEnabled()
    assert not window.sync_action.isEnabled()
    assert not window.diff_action.isEnabled()
    assert window.diff_action.toolTip() == "Calculate Difference in Analysis first"
    assert window.plots_action.toolTip() == "Show Histogram and Line Profile plots"
    assert not window.export_toolbar_action.isEnabled()

    documents = [
        ImageDocument.from_array(
            np.full((8, 10, 3), value, dtype=np.uint8),
            f"toolbar-{index + 1}.png",
        )
        for index, value in enumerate((0, 10, 30))
    ]
    for document in documents:
        window.add_document(document, select=False)

    window._select_document_ids([documents[0].document_id])
    assert window.action_map["Fit Image"].isEnabled()
    assert window.action_map["100% Zoom"].isEnabled()
    assert window.zoom_in_action.isEnabled()
    assert window.zoom_out_action.isEnabled()
    assert not window.sync_action.isEnabled()

    window._select_document_ids([documents[0].document_id, documents[1].document_id])
    assert window.sync_action.isEnabled()
    assert window.sync_action.isChecked()
    assert window.sync_action.toolTip() == "Disable synchronized zoom, pan, and cursor"
    window.sync_action.trigger()
    assert not window.sync_action.isChecked()
    assert window.sync_action.toolTip() == (
        "Synchronize zoom, pan, and cursor across visible images"
    )
    assert not window.diff_action.isEnabled()
    assert window.diff_action.toolTip() == "Calculate Difference in Analysis first"

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None and window.diff_action.isChecked(),
        timeout=3000,
    )
    assert window.diff_action.isEnabled()
    assert window.diff_action.toolTip() == "Hide Difference"

    window.diff_action.trigger()
    assert not window.diff_action.isChecked()
    assert window.diff_action.isEnabled()
    assert window.diff_action.toolTip() == (
        "Show the cached Difference for the selected image pair"
    )

    window.plots_action.trigger()
    assert window.plots_action.isChecked()
    assert window.plots_action.toolTip() == "Hide Histogram and Line Profile plots"
    window.plots_action.trigger()
    assert not window.plots_action.isChecked()
    assert window.plots_action.toolTip() == "Show Histogram and Line Profile plots"

    window._select_document_ids([document.document_id for document in documents])
    window.difference_panel.b_selector.setCurrentIndex(2)
    assert not window.diff_action.isEnabled()
    assert window.diff_action.toolTip() == (
        "Difference is not calculated for the selected pair"
    )
    window.close()
