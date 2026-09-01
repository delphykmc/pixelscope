from __future__ import annotations

import numpy as np
import pytest

from pixelscope.app.main_window import MainWindow
from pixelscope.app.raw_input_compatibility import install_raw_input_compatibility
from pixelscope.app.yuv_input_semantics import install_native_yuv_semantics
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.yuv import NativeYuvFrame

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def make_yuv_document(name: str = "native.yuv") -> ImageDocument:
    return ImageDocument.from_yuv(
        NativeYuvFrame(
            y=np.arange(16, dtype=np.uint8).reshape(4, 4),
            u=np.array([[40, 50], [60, 70]], dtype=np.uint8),
            v=np.array([[180, 190], [200, 210]], dtype=np.uint8),
            layout="YUV420",
        ),
        name,
    )


def make_window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_raw_input_compatibility(window)
    install_native_yuv_semantics(window)
    return window


def test_yuv_statistics_histogram_and_line_controls_use_y_u_v(
    qtbot: object,
) -> None:
    window = make_window(qtbot)
    document = make_yuv_document()

    analysis = window.comparison_analysis_panel
    analysis.set_documents([document], None)
    qtbot.waitUntil(lambda: bool(analysis.last_results))  # type: ignore[attr-defined]

    assert tuple(analysis.channel_buttons) == ("Y", "U", "V")
    assert tuple(button.text() for button in analysis.channel_buttons.values()) == (
        "Y",
        "U",
        "V",
    )
    result = analysis.last_results[0]
    assert result.channel_names == ("Y", "U", "V")
    assert result.channel_sample_counts == (16, 4, 4)

    line = window.line_profile_panel
    line.set_documents([document], LineSelection(0, 0, 3, 0))
    qtbot.waitUntil(lambda: bool(line.last_results))  # type: ignore[attr-defined]

    assert tuple(line.channel_buttons) == ("Y", "U", "V")
    assert line.last_results[0].channel_names == ("Y", "U", "V")
    np.testing.assert_array_equal(line.last_results[0].positions[1], [0.0, 2.0])
    assert not line.view_mode.model().item(2).isEnabled()

    window.close()


def test_yuv_pixel_status_uses_native_values_not_rgb_preview(qtbot: object) -> None:
    window = make_window(qtbot)
    document = make_yuv_document()
    controller = window.native_yuv_semantics_controller

    text = controller.pixel_status_text(
        1,
        1,
        [document.pixel_at(1, 1)],
        [document],
    )

    assert "Y" in text and "U" in text and "V" in text
    assert "Y   5" in text
    assert "U  40" in text
    assert "V 180" in text
    assert document.preview is not None
    assert tuple(int(value) for value in document.preview[1, 1]) != document.pixel_at(1, 1)

    window.close()


def test_yuv_difference_is_explicitly_unsupported_until_wp_c2(qtbot: object) -> None:
    window = make_window(qtbot)
    first = make_yuv_document("a.yuv")
    second = make_yuv_document("b.yuv")

    window.difference_panel.set_documents(
        [first, second],
        (first.document_id, second.document_id),
    )

    assert window.difference_panel.a_selector.count() == 0
    assert window.difference_panel.b_selector.count() == 0
    assert "WP-C2" in window.difference_panel.status.text()

    # A later Calculate request must not overwrite the explicit C2 boundary with a
    # generic "select two images" message or enter legacy RGB/Gray/Bayer math.
    window.difference_panel.calculate_difference()
    assert "WP-C2" in window.difference_panel.status.text()

    window.close()


def test_mixed_yuv_and_rgb_plots_fail_safe_instead_of_mislabeling(qtbot: object) -> None:
    window = make_window(qtbot)
    yuv = make_yuv_document()
    rgb = ImageDocument.from_array(
        np.zeros((4, 4, 3), dtype=np.uint8),
        "rgb.png",
    )

    window.comparison_analysis_panel.set_documents([yuv, rgb], None)
    window.line_profile_panel.set_documents([yuv, rgb], LineSelection(0, 0, 3, 0))

    assert not window.comparison_analysis_panel.last_results
    assert "Mixed YUV/non-YUV" in window.comparison_analysis_panel.status.text()
    assert all(
        button.isHidden()
        for button in window.comparison_analysis_panel.channel_buttons.values()
    )
    assert not window.line_profile_panel.last_results
    assert "Mixed YUV/non-YUV" in window.line_profile_panel.status.text()
    assert all(button.isHidden() for button in window.line_profile_panel.channel_buttons.values())

    window.close()
