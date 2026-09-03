from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPointF

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.difference_panel import DifferencePanel

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _move_cursor(window: MainWindow, x: int, y: int) -> None:
    point = window.viewer.view_box.mapViewToScene(QPointF(x + 0.2, y + 0.2))
    window.viewer._on_scene_mouse_moved(point)


def test_production_single_view_inspects_reference_mapped_yuv420_u_sample(
    qtbot: object,
) -> None:
    window = _window(qtbot)
    source = ImageDocument.from_yuv(
        NativeYuvFrame(
            y=np.arange(16, dtype=np.uint8).reshape(4, 4),
            u=np.array([[40, 50], [60, 70]], dtype=np.uint8),
            v=np.array([[180, 190], [200, 210]], dtype=np.uint8),
            layout="YUV420",
        ),
        "native.yuv",
    )
    u_view = next(view for view in split_document_channels(source) if view.sample_channel == "U")
    window.viewer.set_document(u_view)

    _move_cursor(window, 3, 3)

    assert window.structured_status.coordinate.text() == "Position (   3,    3)"
    assert "U   70" in window.structured_status.pixel_value.text()
    assert "—" not in window.structured_status.pixel_value.text()
    window.close()


def test_production_single_view_inspects_bayer_point_lattice_valid_and_invalid_sites(
    qtbot: object,
) -> None:
    window = _window(qtbot)
    source = np.arange(35, dtype=np.uint16).reshape(5, 7)
    profile = RawProfile(
        name="raw",
        width=7,
        height=5,
        stride_bytes=14,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=10,
        bit_alignment="lsb",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=0,
        white_level=1023,
    )
    document = ImageDocument.from_array(
        source,
        "raw",
        channel_layout="BAYER",
        raw_profile=profile,
        prepared_preview=render_bayer_preview(source, "RGGB", 0, 10),
    )
    red_view = next(
        view for view in split_document_channels(document) if view.sample_channel == "R"
    )
    window.viewer.set_document(red_view)

    _move_cursor(window, 1, 0)
    assert window.structured_status.coordinate.text() == "Position (   1,    0)"
    assert window.structured_status.pixel_value.text().endswith("—")

    _move_cursor(window, 0, 0)
    assert window.structured_status.coordinate.text() == "Position (   0,    0)"
    assert "R    0" in window.structured_status.pixel_value.text()
    assert "—" not in window.structured_status.pixel_value.text()
    window.close()


def test_difference_mapping_survives_zero_residency_and_rejects_stale_payload(
    qtbot: object,
) -> None:
    y = np.zeros((4, 4), dtype=np.uint8)
    first = ImageDocument.from_yuv(
        NativeYuvFrame(
            y=y.copy(),
            u=np.zeros((2, 2), dtype=np.uint8),
            v=np.zeros((2, 2), dtype=np.uint8),
            layout="YUV420",
        ),
        "a.yuv",
    )
    second = ImageDocument.from_yuv(
        NativeYuvFrame(
            y=y.copy(),
            u=np.full((2, 2), 7, dtype=np.uint8),
            v=np.zeros((2, 2), dtype=np.uint8),
            layout="YUV420",
        ),
        "b.yuv",
    )
    panel = DifferencePanel(difference_cache_budget_bytes=1)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([first, second], (first.document_id, second.document_id))
    panel.channel.setCurrentText("U")
    published: list[tuple[object, object]] = []
    panel.result_ready.connect(
        lambda _title, numerical, preview: published.append((numerical, preview))
    )

    panel.calculate_difference()
    qtbot.waitUntil(lambda: len(published) == 1, timeout=3000)  # type: ignore[attr-defined]

    numerical, preview = published[0]
    assert panel.difference_cache.entry_count == 0
    mapping = panel.mapping_snapshot_for_payload(numerical, preview)
    assert mapping is not None
    assert mapping.channel == "U"
    assert mapping.spatial_sampling.semantics == "cell_footprint"
    assert mapping.spatial_sampling.reference_shape == (4, 4)
    assert mapping.spatial_sampling.sample_shape == (2, 2)

    assert panel.mapping_snapshot_for_payload(np.asarray(numerical).copy(), preview) is None
    panel.channel.setCurrentText("Y")
    assert panel.mapping_snapshot_for_payload(numerical, preview) is None

    panel.close()


def test_bayer_difference_mapping_survives_zero_residency(
    qtbot: object,
) -> None:
    profile = RawProfile(
        name="raw",
        width=7,
        height=5,
        stride_bytes=14,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=10,
        bit_alignment="lsb",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=0,
        white_level=1023,
    )
    source = np.arange(35, dtype=np.uint16).reshape(5, 7)
    first = ImageDocument.from_array(
        source,
        "a.raw",
        channel_layout="BAYER",
        bit_depth=10,
        raw_profile=profile,
        prepared_preview=render_bayer_preview(source, "RGGB", 0, 10),
    )
    second_source = source + np.uint16(1)
    second = ImageDocument.from_array(
        second_source,
        "b.raw",
        channel_layout="BAYER",
        bit_depth=10,
        raw_profile=profile,
        prepared_preview=render_bayer_preview(second_source, "RGGB", 0, 10),
    )
    panel = DifferencePanel(difference_cache_budget_bytes=1)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([first, second], (first.document_id, second.document_id))
    panel.channel.setCurrentText("B")
    published: list[tuple[object, object]] = []
    panel.result_ready.connect(
        lambda _title, numerical, preview: published.append((numerical, preview))
    )

    panel.calculate_difference()
    qtbot.waitUntil(lambda: len(published) == 1, timeout=3000)  # type: ignore[attr-defined]

    numerical, preview = published[0]
    assert panel.difference_cache.entry_count == 0
    mapping = panel.mapping_snapshot_for_payload(numerical, preview)
    assert mapping is not None
    assert mapping.channel == "B"
    sampling = mapping.spatial_sampling
    assert sampling.semantics == "point_lattice"
    assert (sampling.row_phase, sampling.column_phase) == (1, 1)
    assert sampling.sample_shape == (2, 3)
    assert sampling.reference_shape == (5, 7)

    panel.close()
