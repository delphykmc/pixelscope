"""Role labels, resize-stable navigation and shared source-pixel inspection."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QColor, QImage

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow


def _result(source_a: Path | None = None, source_b: Path | None = None) -> AnalysisResult:
    grid = SpatialMap(
        values=np.array([[3.0, -2.0], [1.0, 7.0]]),
        valid_mask=np.array([[True, True], [True, False]]),
        image_width=128,
        image_height=128,
        block_width=64,
        block_height=64,
    )
    metric = AttributeDisplay(
        "detail",
        "Detail",
        "dB",
        "Detail",
        1.5,
        "available",
        True,
        5.0,
        grid,
        chart_axis_range=5.0,
        summary_signal_gate=True,
    )
    return AnalysisResult(
        "role-fixture",
        128,
        128,
        "ref.png",
        "target.png",
        (metric,),
        source_a=source_a,
        source_b=source_b,
    )


def _write_rgb(path: Path, color: tuple[int, int, int]) -> None:
    image = QImage(128, 128, QImage.Format.Format_RGB32)
    image.fill(QColor(*color))
    assert image.save(str(path))


def test_source_role_names_are_opt_in_and_do_not_change_scientific_identity(qtbot: object) -> None:
    baseline = _result()
    assert baseline.source_a_role is None and baseline.source_b_role is None
    with pytest.raises(ValueError, match="source role names"):
        replace(baseline, source_a_role="  ")
    with pytest.raises(ValueError, match="source role names"):
        replace(baseline, source_b_role="Target\nInjected")

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(baseline)
    # Request 1's title precedence: source labels first, role labels optional.
    assert win.windowTitle() == "IQA Analysis — ref.png vs target.png"
    assert win.pair_summary.text().startswith("A: ref.png  /  B: target.png")

    win2 = AnalysisWindow()
    qtbot.addWidget(win2)  # type: ignore[attr-defined]
    named = replace(baseline, source_a_role="Reference", source_b_role="Target")
    win2.present_result(named)
    assert "Reference: ref.png vs Target: target.png" in win2.windowTitle()
    assert "Reference: ref.png" in win2.pair_summary.text()
    assert "Target: target.png" in win2.pair_summary.text()
    assert win2._pane_labels[0].toolTip().startswith("REFERENCE")
    assert win2._pane_labels[1].toolTip().startswith("TARGET")
    assert win2.spatial_panel.previews[0]._source_roles == ("Reference", "Target")
    assert "Reference/Target ROI" in win2.spatial_panel.status_label.text()
    assert named.attributes is baseline.attributes
    assert named.source_a_label == baseline.source_a_label
    # Integrated request 1 permits missing source labels without bypassing
    # the immutable result model, while request 3 keeps role metadata valid.
    missing_label = replace(named, result_id="role-fallback", source_a_label="  ")
    win2.present_result(missing_label)
    assert win2.windowTitle() == "IQA Analysis — role-fallback"
    win.close()
    win2.close()


def test_view_resize_retains_logical_center_and_does_not_broadcast(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(_result())
    win.show()
    qtbot.waitUntil(lambda: win._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]

    source = win._views[0]
    source.apply_navigation(2.0, 63.25, 70.75)
    win._sync_views(source, 2.0, 63.25, 70.75)
    emitted: list[tuple[float, float, float]] = []
    for view in win._views:
        view.navigation_changed.connect(lambda scale, x, y: emitted.append((scale, x, y)))

    for _ in range(8):
        win._image_split.setSizes([220, 360, 280])
        win.resize(1540, 850)
        qtbot.wait(5)  # type: ignore[attr-defined]
        assert len({view.viewport().width() for view in win._views}) > 1
        win._image_split.setSizes([330, 215, 290])
        win.resize(1380, 780)
        qtbot.wait(5)  # type: ignore[attr-defined]

    assert emitted == []
    assert all(view._navigation_center == QPointF(63.25, 70.75) for view in win._views)
    assert all(view.transform().m11() == pytest.approx(2.0) for view in win._views)
    state = win._state()
    assert state is not None
    assert (state.center_x, state.center_y) == (63.25, 70.75)
    win.close()


def test_hover_links_three_guides_and_reads_rgb_and_masked_map(
    qtbot: object, tmp_path: Path
) -> None:
    source_a = tmp_path / "ref.png"
    source_b = tmp_path / "target.png"
    _write_rgb(source_a, (17, 33, 65))
    _write_rgb(source_b, (111, 127, 201))
    result = replace(_result(source_a, source_b), source_a_role="Reference", source_b_role="Target")
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    emitted: list[tuple[str, str, str, str]] = []
    clears: list[bool] = []
    win.hover_readout_changed.connect(lambda *fields: emitted.append(fields))
    win.hover_readout_cleared.connect(lambda: clears.append(True))
    win.present_result(result)
    win.show()
    qtbot.waitUntil(lambda: win._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]

    for view in win._views:
        position = view.mapFromScene(QPointF(16.5, 16.5))
        assert view.viewport().rect().contains(position)
        qtbot.mouseMove(view.viewport(), pos=position)  # type: ignore[attr-defined]
        assert win._hovered_pixel == (16, 16)
        assert len(win._guide_items) == 3
        for vertical, horizontal in win._guide_items:
            assert vertical.isVisible() and horizontal.isVisible()
            assert vertical.line().x1() == 16.5
            assert horizontal.line().y1() == 16.5
        readout = win._hover_readouts.values.toolTip()
        assert "Reference RGB8: 17, 33, 65" in readout
        assert "Target RGB8: 111, 127, 201" in readout
        assert "Detail Map [0, 0]: +3.0000 dB" in readout
        assert emitted[-1][0] == "Pixel (16, 16)"
        assert emitted[-1][1] == "Reference RGB8: 17, 33, 65"
        assert emitted[-1][2] == "Target RGB8: 111, 127, 201"
        assert emitted[-1][3] == "Detail Map [0, 0]: +3.0000 dB"

    win._views[2]._report_hover(win._views[2].mapFromScene(QPointF(100.5, 100.5)))
    assert "Detail Map [1, 1]: invalid" in win._hover_readouts.values.toolTip()
    win._views[2]._report_hover(QPoint(-10000, -10000))
    assert win._hovered_pixel is None
    assert clears
    assert not any(v.isVisible() or h.isVisible() for v, h in win._guide_items)
    win.close()


def test_hover_fields_cover_missing_source_and_attribute_transition(
    qtbot: object, tmp_path: Path
) -> None:
    source_a = tmp_path / "ref.png"
    _write_rgb(source_a, (8, 16, 32))
    original = _result(source_a=source_a)
    alternate = replace(original.attributes[0], attribute_id="alternate", label="Other metric")
    result = replace(original, attributes=(*original.attributes, alternate))
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    fields: list[tuple[str, str, str, str]] = []
    win.hover_readout_changed.connect(lambda *values: fields.append(values))
    win.present_result(result)
    win._show_hover_pixel(16, 16)
    assert fields[-1][0] == "Pixel (16, 16)"
    assert fields[-1][1] == "Image A RGB8: 8, 16, 32"
    assert fields[-1][2] == "Image B RGB: unavailable"
    assert fields[-1][3] == "Detail Map [0, 0]: +3.0000 dB"

    win._group_tables["dB"].setCurrentCell(1, 0)
    assert fields[-1][3] == "Other metric Map [0, 0]: +3.0000 dB"
    assert fields[-1][2] == "Image B RGB: unavailable"
    win.close()
