"""Combined request 1/2/3/4 regression: signed data, verdict tint and UI roles."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from pixelscope_enterprise.iqa.analysis_model import (
    NEUTRAL_PRESENTATION_RGB,
    AnalysisResult,
    AttributeDisplay,
    SpatialMap,
    apply_spatial_reference_tint_rgba,
    roi_statistics,
    spatial_display_half_range,
)
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow, _map_pixmap
from pixelscope_enterprise.iqa.hover_fields import format_source_rgb_field
from pixelscope_enterprise.iqa.quality_presentation import (
    MUTED_RGB,
    NEUTRAL_RGB,
    quality_spatial_rgba,
)
from pixelscope_enterprise.iqa.visual_export import write_visual_pngs


def _quality_result(tmp_path: Path):
    a = tmp_path / "ref.png"
    b = tmp_path / "target.png"
    for path, rgb in ((a, (17, 33, 65)), (b, (111, 127, 201))):
        image = QImage(128, 128, QImage.Format.Format_RGB32)
        image.fill(QColor(*rgb))
        assert image.save(str(path))
    grid = SpatialMap(
        values=np.array([[2.0, -2.0, 0.5], [-0.5, 0.0, 3.0]]),
        valid_mask=np.array([[True, True, True], [True, True, False]]),
        image_width=128,
        image_height=128,
        block_width=128 / 3,
        block_height=64,
    )
    oriented = AttributeDisplay(
        "detail",
        "Detail",
        "dB",
        "Detail",
        2.0,
        "available",
        True,
        5.0,
        grid,
        chart_axis_range=5.0,
        summary_signal_gate=True,
        quality_direction="higher_is_better",
    )
    neutral = replace(
        oriented,
        attribute_id="neutral",
        label="Neutral",
        quality_direction="none",
        quality_oriented=False,
        official_value=4.0,
    )
    unknown = replace(
        oriented,
        attribute_id="unknown",
        label="Unknown",
        quality_direction="lower_is_better",
        summary_signal_gate=None,
        official_value=-3.0,
    )
    return AnalysisResult(
        "quality-integrated",
        128,
        128,
        "reference_" + "long-scene_" * 25 + ".png",
        "target.png",
        (oriented, neutral, unknown),
        source_a=a,
        source_b=b,
        source_a_role="Reference",
        source_b_role="Target",
    )


def test_quality_and_reference_tint_are_applied_once_with_role_ui_and_exports(
    qtbot: object, tmp_path: Path
) -> None:
    result = _quality_result(tmp_path)
    attribute = result.attributes[0]
    assert attribute.spatial is not None
    values_before = attribute.spatial.values.copy()
    mask_before = attribute.spatial.valid_mask.copy()
    stats_before = roi_statistics(attribute.spatial, (0, 0, 128, 128))

    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.resize(1440, 800)
    window.present_result(result)
    window.show()
    qtbot.waitUntil(lambda: window._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]
    assert not window.quality_policy_action.isChecked()
    assert not window.map_reference_action.isChecked()
    assert "Reference: reference_" in window.windowTitle()
    assert "Target: target.png" in window.windowTitle()
    assert "…" in window._pane_labels[0].text()
    assert window._pane_labels[0].toolTip().startswith("REFERENCE  ·  reference_")
    assert "positive signed" in " ".join(card.text() for card in window.top3_buttons)
    assert "neutral" not in window._top3_attribute_ids  # request 3 legacy orientation

    window._set_roi(0, 0, 64, 64)
    state_before = window.current_analysis_state()
    roi_before = window.roi_label.text()
    state = window._state()
    assert state is not None
    images = (QImage(str(result.source_a)), QImage(str(result.source_b)))
    options = dict(
        scope="both",
        roi=window.current_roi,
        display_range=window._display_range(attribute, state),
        display_gain=state.display_gain,
    )
    before = write_visual_pngs(
        result,
        attribute,
        images,
        tmp_path / "before",
        **options,  # type: ignore[arg-type]
    )

    window.quality_policy_action.setChecked(True)
    window.map_reference_action.setChecked(True)
    assert window._map_reference_item is not None
    assert window._map_reference_item.isVisible()
    assert window._map_item is not None
    assert "Superior" in " ".join(card.text() for card in window.top3_buttons)
    assert "neutral" not in window._top3_attribute_ids  # request 2 explicit direction
    assert window._top3_attribute_ids == ["detail"]
    assert window.top3_buttons[0].property("insightTone") == "superior"
    assert not window.top3_buttons[1].isEnabled()

    half_range = spatial_display_half_range(
        window._display_range(attribute, state), state.display_gain
    )
    quality = quality_spatial_rgba(attribute, half_range)
    assert quality is not None
    expected = apply_spatial_reference_tint_rgba(attribute, half_range, quality)
    pixels = window._map_item.pixmap().toImage()
    assert (pixels.width(), pixels.height()) == (3, 2)
    for y in range(2):
        for x in range(3):
            actual = pixels.pixelColor(x, y)
            # QPixmap may lose precision through premultiplied-alpha
            # conversion, especially for faint gray / transparent cells.
            # Its alpha remains exact, which is the double-attenuation guard.
            assert actual.alpha() == expected[y, x, 3]
            if actual.alpha() >= 32:
                assert all(
                    abs(current - int(want)) <= 4
                    for current, want in zip(
                        (actual.red(), actual.green(), actual.blue()),
                        expected[y, x, :3],
                        strict=True,
                    )
                )
    assert expected[0, 0, 3] > 0
    assert expected[0, 1, 3] > 0
    assert 0 < expected[0, 2, 3] < expected[0, 0, 3]
    assert 0 < expected[1, 0, 3] < expected[0, 0, 3]
    assert tuple(expected[0, 2, :3]) != MUTED_RGB  # ±0.5 is visible
    assert expected[1, 1, 3] == 0  # signed zero reveals source A
    assert expected[1, 2, 3] == 0  # invalid cell reveals source A
    # A second alpha multiplication would make this strictly smaller.
    assert expected[0, 0, 3] > int(round(expected[0, 0, 3] * 176 / 255))
    underlay = window._map_reference_item.pixmap().toImage().pixelColor(10, 10)
    assert underlay.red() == underlay.green() == underlay.blue()

    hover: list[tuple[str, str, str, str]] = []
    window.hover_readout_changed.connect(lambda *fields: hover.append(fields))
    window._show_hover_pixel(16, 16)
    assert hover[-1][1] == format_source_rgb_field("Reference", (17, 33, 65), bit_depth=8)
    assert hover[-1][2] == format_source_rgb_field("Target", (111, 127, 201), bit_depth=8)
    assert hover[-1][3] == "Detail Map [0, 0]: +2.0000 dB"

    window._image_split.setSizes([250, 390, 280])
    QApplication.processEvents()
    sizes = window._image_split.sizes()
    for view in window._views:
        view.apply_navigation(2.0, 63.25, 70.75)
    navigation: list[tuple[float, float, float]] = []
    for view in window._views:
        view.navigation_changed.connect(lambda *coords: navigation.append(coords))
    expected_centers: list[QPointF] | None = None
    for _ in range(2):
        window.swap_sources_action.trigger()
        QApplication.processEvents()
        # Small 128px sources are fit/clamped to image center on swap.
        # Repeated resize must not accumulate further center drift.
        if expected_centers is None:
            expected_centers = [view._navigation_center for view in window._views]
        assert all(abs(a - b) <= 2 for a, b in zip(window._image_split.sizes(), sizes, strict=True))
        window.resize(1530, 850)
        qtbot.wait(5)  # type: ignore[attr-defined]
        window.resize(1440, 800)
        qtbot.wait(5)  # type: ignore[attr-defined]
        assert [view._navigation_center for view in window._views] == expected_centers
    assert navigation == []
    assert expected_centers == [QPointF(64.0, 64.0)] * 3
    assert window.roi_label.text() == roi_before
    assert window.current_analysis_state() == state_before

    after = write_visual_pngs(
        result,
        attribute,
        images,
        tmp_path / "after",
        **options,  # type: ignore[arg-type]
    )
    files = sorted(path.name for path in before.iterdir())
    assert files == sorted(path.name for path in after.iterdir())
    assert all((before / name).read_bytes() == (after / name).read_bytes() for name in files)
    np.testing.assert_array_equal(attribute.spatial.values, values_before)
    np.testing.assert_array_equal(attribute.spatial.valid_mask, mask_before)
    assert roi_statistics(attribute.spatial, (0, 0, 128, 128)) == stats_before
    window.close()


def test_neutral_and_untrusted_palette_share_request4_constants_and_request1_tint(
    tmp_path: Path, qtbot: object
) -> None:
    result = _quality_result(tmp_path)
    neutral, untrusted = result.attributes[1:]
    assert NEUTRAL_RGB == NEUTRAL_PRESENTATION_RGB == (94, 94, 94)
    normal_neutral = quality_spatial_rgba(neutral, 2.0)
    normal_untrusted = quality_spatial_rgba(untrusted, 2.0)
    assert normal_neutral is not None and normal_untrusted is not None
    assert tuple(normal_neutral[0, 0, :3]) == NEUTRAL_PRESENTATION_RGB
    assert tuple(normal_untrusted[0, 0, :3]) == MUTED_RGB
    assert normal_neutral[0, 0, 3] > normal_untrusted[0, 0, 3]

    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.present_result(result)
    window.set_quality_presentation(True)
    window.map_reference_action.setChecked(True)
    state = window._state()
    assert state is not None
    for attribute in (neutral, untrusted):
        state.attribute_id = attribute.attribute_id
        window._select_active_attribute()
        window._render_result()
        assert window._map_item is not None
        assert window._map_reference_item is not None
        half_range = spatial_display_half_range(
            window._display_range(attribute, state), state.display_gain
        )
        expected = _map_pixmap(attribute, half_range, translucent=True, quality_policy=True)
        assert expected is not None
        assert window._map_item.pixmap().toImage() == expected.toImage()
    window.close()
