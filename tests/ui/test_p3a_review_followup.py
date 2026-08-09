from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.settings import (
    MAX_DIFFERENCE_THRESHOLD,
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)
from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.difference_panel import DifferencePanel
from pixelscope.ui.settings_dialog import SettingsDialog


def _gray(value: int, name: str, bit_depth: int) -> ImageDocument:
    dtype = np.uint8 if bit_depth <= 8 else np.uint16
    return ImageDocument.from_array(
        np.full((6, 8), value, dtype=dtype),
        name,
        bit_depth=bit_depth,
    )


def _bayer(value: int, name: str, bit_depth: int) -> ImageDocument:
    source = np.full((6, 8), value, dtype=np.uint16)
    full_scale = (1 << bit_depth) - 1
    profile = RawProfile(
        name=name,
        width=8,
        height=6,
        dtype="uint16",
        stride_bytes=16,
        bit_depth=bit_depth,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=0,
        white_level=full_scale,
    )
    transform = DisplayTransform(black_level=0, white_level=full_scale)
    return ImageDocument.from_array(
        source,
        name,
        channel_layout="BAYER",
        bit_depth=bit_depth,
        raw_profile=profile,
        display_transform=transform,
        prepared_preview=render_bayer_preview(source, transform),
    )


def test_native_threshold_uses_uint16_bound_and_survives_domain_switch(
    qtbot: object,
) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    gray8_a = _gray(0, "a.png", 8)
    gray8_b = _gray(1, "b.png", 8)
    gray10 = _gray(1, "c.raw", 10)

    panel.set_display_defaults(MAX_DIFFERENCE_THRESHOLD, 1)
    panel.set_documents(
        [gray8_a, gray8_b, gray10],
        (gray8_a.document_id, gray8_b.document_id),
    )

    assert panel.threshold.maximum() == float(MAX_DIFFERENCE_THRESHOLD)
    assert panel.threshold.value() == float(MAX_DIFFERENCE_THRESHOLD)
    assert panel.threshold.suffix() == " code"

    panel.b_selector.setCurrentIndex(2)
    assert panel.threshold.maximum() == pytest.approx(100.0)
    assert panel.threshold.suffix() == " %FS"

    panel.b_selector.setCurrentIndex(1)
    assert panel.threshold.maximum() == float(MAX_DIFFERENCE_THRESHOLD)
    assert panel.threshold.value() == float(MAX_DIFFERENCE_THRESHOLD)


def test_settings_dialog_uses_same_native_threshold_bound(
    qtbot: object,
    tmp_path: Path,
) -> None:
    qsettings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    repository = SettingsRepository(QSettingsAdapter(qsettings))
    initial = ApplicationSettings()
    dialog = SettingsDialog(
        repository,
        initial,
        initial.performance_settings(),
        physical_memory_bytes=16 * 1024**3,
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.difference_threshold.minimum() == 0
    assert dialog.difference_threshold.maximum() == MAX_DIFFERENCE_THRESHOLD


def test_mixed_bit_bayer_same_cfa_supports_plane_roi_in_normalized_domain(
    qtbot: object,
) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _bayer(0, "a.raw", 10)
    second = _bayer((1 << 12) - 1, "b.raw", 12)
    roi = RoiBounds(0, 0, 4, 4)

    panel.set_documents(
        [first, second],
        (first.document_id, second.document_id),
        active_roi=roi,
    )

    assert panel.domain_status.text() == "Domain Normalized [0–1]"
    assert [panel.channel.itemText(i) for i in range(panel.channel.count())] == [
        "Mosaic",
        "R",
        "Gr",
        "Gb",
        "B",
    ]
    assert panel.region.currentText() == "Active ROI"
    assert panel.channel.currentText() == "Mosaic"
    assert panel.metric_scope.text() == "Scope Active ROI · Bayer mosaic"

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: (
            panel.last_result is not None and panel.difference_cache.entry_count == 1
        ),
        timeout=3000,
    )

    cached = panel.cached_result_for_current()
    assert cached is not None
    assert cached.domain == "normalized"
    assert cached.channel_layout == "BAYER"
    assert cached.bayer_pattern == "RGGB"
    assert cached.absolute.dtype == np.dtype(np.float32)
    assert np.all(cached.absolute == 1.0)
    assert panel.last_result is not None
    assert panel.last_result.maximum_absolute == pytest.approx(1.0)

    panel.channel.setCurrentText("R")

    assert panel.metric_scope.text() == "Scope Active ROI · Bayer R"
    assert panel.difference_cache.entry_count == 1
    assert panel.last_result is not None
    assert panel.last_result.maximum_absolute == pytest.approx(1.0)
