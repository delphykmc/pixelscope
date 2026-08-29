from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea, QTabWidget

from pixelscope.app.settings import QSettingsAdapter, SettingsRepository
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel
from pixelscope.ui.line_profile_panel import LineProfilePanel
from pixelscope.ui.raw_open_dialog import RawOpenDialog
from pixelscope.ui.settings_dialog import SettingsDialog
from pixelscope.ui.structured_status_bar import StructuredStatusBar

pytestmark = pytest.mark.usefixtures("isolated_synced_qsettings")


def _repository() -> SettingsRepository:
    return SettingsRepository(QSettingsAdapter(QSettings()))


def test_inactive_plot_page_does_not_force_one_row_control_width(qtbot: object) -> None:
    analysis = ComparisonAnalysisPanel()
    line = LineProfilePanel()
    tabs = QTabWidget()
    tabs.addTab(analysis.histogram_panel, "Histogram")
    tabs.addTab(line, "Line Profile")
    qtbot.addWidget(tabs)  # type: ignore[attr-defined]
    tabs.resize(640, 360)
    tabs.show()

    line_combo_widths = sum(
        combo.minimumSizeHint().width()
        for combo in (line.view_mode, line.y_mode, line.x_mode, line.reference_selector)
    )
    histogram_combo_widths = sum(
        combo.minimumSizeHint().width()
        for combo in (
            analysis.histogram_mode,
            analysis.histogram_units,
            analysis.histogram_range,
            analysis.histogram_bins,
        )
    )
    assert line.minimumSizeHint().width() < line_combo_widths
    assert analysis.histogram_panel.minimumSizeHint().width() < histogram_combo_widths

    tabs.setCurrentWidget(line)
    documents = [
        ImageDocument.from_array(
            np.zeros((4, 8, 3), dtype=np.uint8),
            f"reference-{index}.png",
        )
        for index in range(2)
    ]
    line.set_documents(documents, None)
    line.y_mode.setCurrentText("Difference from reference")
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert line.view_mode.isVisible() and line.view_mode.width() > 0
    assert line.y_mode.isVisible() and line.y_mode.width() > 0
    assert line.x_mode.isVisible() and line.x_mode.width() > 0
    assert line.reference_selector.isVisible() and line.reference_selector.width() > 0
    assert all(
        button.isVisible() and button.width() > 0 for button in line.channel_buttons.values()
    )
    assert line.view_mode.geometry().y() < line.x_mode.geometry().y()
    assert line.status.geometry().y() > line.x_mode.geometry().y()

    full_status = "Line profile coordinates " + "1234567890" * 20
    line._set_status(full_status)
    assert line.status.text() == full_status
    assert line.status.toolTip() == full_status
    assert line.status.accessibleName() == full_status


def test_structured_status_long_values_do_not_expand_minimum_hint(qtbot: object) -> None:
    status = StructuredStatusBar()
    qtbot.addWidget(status)  # type: ignore[attr-defined]
    status.resize(640, status.sizeHint().height())
    status.show()
    image_info = "RGB · 1920×1080 · 8-bit"
    status.set_active_document("short.png", image_info)
    baseline_width = status.minimumSizeHint().width()

    filename = "long-folder/" * 30 + "reference-image-with-a-long-name.png"
    pixels = " · ".join(f"{index} (R 255, G 255, B 255)" for index in range(1, 7))
    status.set_active_document(filename, image_info)
    status.pixel_value.setText(pixels)
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert status.minimumSizeHint().width() == baseline_width
    assert status.active_file.text() == filename
    assert status.active_file.toolTip() == filename
    assert status.active_file.accessibleName() == filename
    assert status.pixel_value.text() == pixels
    assert status.pixel_value.toolTip() == pixels
    assert status.pixel_value.accessibleDescription() == pixels
    assert status.active_file._paint_text() != filename
    assert status.pixel_value._paint_text() != pixels


def test_raw_dialog_can_shrink_and_scroll_without_hiding_footer(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    initial_height = dialog.height()

    dialog.resize(dialog.width() + 80, initial_height // 2)
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert dialog.isSizeGripEnabled()
    assert dialog.minimumWidth() < dialog.maximumWidth()
    assert dialog.height() < initial_height
    assert dialog.body_scroll.verticalScrollBar().maximum() > 0
    assert dialog.footer.isVisible()
    assert dialog.ok_button.isVisible()
    assert dialog.cancel_button.isVisible()


def test_settings_dialog_yields_below_previous_hard_floor(qtbot: object) -> None:
    repository = _repository()
    initial = repository.load()
    dialog = SettingsDialog(
        repository,
        initial,
        initial.performance_settings(),
        physical_memory_bytes=16 * 1024**3,
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    dialog.resize(640, 420)
    dialog.category_list.setCurrentRow(2)
    qtbot.wait(20)  # type: ignore[attr-defined]

    current_page = dialog.page_stack.currentWidget()
    assert isinstance(current_page, QScrollArea)
    assert dialog.minimumWidth() < 820
    assert dialog.minimumHeight() < 540
    assert dialog.width() < 820
    assert dialog.height() < 540
    assert current_page.verticalScrollBar().maximum() > 0
    assert dialog.reset_button.isVisible()
    save = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    cancel = dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert save is not None and save.isVisible()
    assert cancel is not None and cancel.isVisible()
