from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QComboBox, QSizePolicy, QWidget

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument


def _production_window(qtbot: object, *, enlarge_font: bool = False) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    if enlarge_font:
        font = window.font()
        point_size = font.pointSizeF()
        font.setPointSizeF(max(16.0, point_size * 1.75 if point_size > 0 else 16.0))
        window.setFont(font)
    _compose_main_window_presentation(window)
    window.show()
    return window


def _register_pair(window: MainWindow, tmp_path: Path) -> tuple[ImageDocument, ImageDocument]:
    documents = tuple(
        ImageDocument.from_array(
            np.full((12, 16, 3), index * 32, dtype=np.uint8),
            f"pair_{index}.png",
            source_path=tmp_path / f"pair_{index}.png",
        )
        for index in range(2)
    )
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    return documents  # type: ignore[return-value]


def _assert_combo_content_floor(combo: QComboBox) -> None:
    assert combo.sizeAdjustPolicy() == QComboBox.SizeAdjustPolicy.AdjustToContents
    assert combo.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.MinimumExpanding
    assert combo.minimumWidth() > combo.sizeHint().width()
    assert combo.width() >= combo.minimumWidth()


def _assert_group_content_floor(group: QWidget) -> None:
    layout = group.layout()
    assert layout is not None
    assert group.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.MinimumExpanding
    assert group.minimumWidth() >= layout.minimumSize().width()
    assert group.width() >= group.minimumWidth()


def _assert_action_content_floors(window: MainWindow) -> None:
    review = window.review_selection_controller
    assert review.clear_button.text() == "Clear"
    assert review.keep_button.text() == "Keep"
    assert review.clear_button.accessibleName() == "Clear Selection"
    assert review.keep_button.accessibleName() == "Keep Selection"

    for button in (review.clear_button, review.keep_button):
        assert button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Minimum
        assert button.minimumWidth() >= button.sizeHint().width()
        assert button.width() >= button.minimumWidth()

    layout_combo = window.layout_selector
    layout_group = layout_combo.parentWidget()
    gain_combo = window.findChild(QComboBox, "DisplayGainCombo")
    gain_group = window.findChild(QWidget, "DisplayGainControl")
    assert isinstance(layout_group, QWidget)
    assert gain_combo is not None
    assert gain_group is not None

    _assert_combo_content_floor(layout_combo)
    _assert_combo_content_floor(gain_combo)
    _assert_group_content_floor(layout_group)
    _assert_group_content_floor(gain_group)

    assert layout_combo.findText("Single View") >= 0
    assert layout_combo.findText("Multi View") >= 0
    assert gain_combo.findText("16×") >= 0


def test_command_row_keeps_compact_actions_and_native_combo_chrome_visible(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    _register_pair(window, tmp_path)

    # Approximate the logical work-area pressure of FHD at 200% scaling. The
    # workspace may choose its own minimum width, but actionable controls must
    # never be allocated below their polished content floors.
    window.resize(960, 540)
    qtbot.wait(20)  # type: ignore[attr-defined]
    _assert_action_content_floors(window)
    window.close()


def test_command_row_content_floors_follow_larger_font_metrics(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot, enlarge_font=True)
    _register_pair(window, tmp_path)
    window.resize(1280, 720)
    qtbot.wait(20)  # type: ignore[attr-defined]

    # This is deliberately font-metric based rather than a hard-coded pixel
    # assertion so the contract follows the real platform style/font at runtime.
    _assert_action_content_floors(window)
    window.close()
