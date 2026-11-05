"""W07 UI contract: typed Pivot is read-only and legacy Raw export remains intact."""
from __future__ import annotations

import csv
import gc
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QTableWidgetSelectionRange

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel
from pixelscope.ui.difference_panel import DifferencePanel


def _document(name: str, value: int, *, dtype: object = np.uint8) -> ImageDocument:
    return ImageDocument.from_array(np.full((8, 8, 3), value, dtype=dtype), name)


def _ready(panel: ComparisonAnalysisPanel, qtbot: object) -> None:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.get_current_statistics_pivot() is not None,
        timeout=5000,
    )


def _row(panel: ComparisonAnalysisPanel, name: str) -> int:
    for index in range(panel.pivot_table.rowCount()):
        item = panel.pivot_table.item(index, 0)
        if item is not None and item.text() == name:
            return index
    raise AssertionError(f"missing Pivot metric/channel {name}")


def test_raw_pivot_switch_reference_delta_copy_and_legacy_export(
    qtbot: object, tmp_path: Path
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.show()
    documents = [_document("기준.png", 10), _document("대상.png", 17)]
    panel.set_documents(documents, None)
    _ready(panel, qtbot)
    assert panel.statistics_view.currentText() == "Raw"
    assert panel.statistics_stack.currentWidget() is panel.table
    legacy_path = tmp_path / "old.csv"
    panel.export_csv(legacy_path)
    legacy = legacy_path.read_text(encoding="utf-8-sig")
    assert legacy.startswith("Id,Image,Bit depth,Samples")
    assert "Id,Ch,Min,Max,Mean,Std,P1,P50,P99" in legacy

    panel.statistics_view.setCurrentText("Pivot")
    assert panel.statistics_stack.currentWidget() is panel.pivot_table
    assert panel.pivot_table.columnCount() == 4
    assert panel.pivot_table.rowCount() == 9  # Mean, Std, P99 × RGB
    assert "기준.png" in panel.pivot_table.horizontalHeaderItem(2).text()
    panel.pivot_reference.setCurrentIndex(1)
    panel.pivot_delta.setCurrentText("Absolute Δ")
    mean_r = _row(panel, "Mean · R")
    item = panel.pivot_table.item(mean_r, 3)
    assert item is not None
    assert "Δ 7 native code" in item.text()
    assert "Native samples: 64" in item.toolTip()
    assert "17" in item.toolTip()

    panel.pivot_table.selectRow(mean_r)
    panel.copy_selection()
    copied = QApplication.clipboard().text()
    assert copied.splitlines()[0].split("\t")[:2] == ["Metric", "Unit"]
    assert "Mean · R\tnative code" in copied
    assert "Delta 7 native code" in copied

    pivot_path = tmp_path / "pivot.csv"
    panel.export_pivot_csv(pivot_path)
    with pivot_path.open(encoding="utf-8-sig", newline="") as stream:
        content = list(csv.reader(stream))
    assert content[0][:3] == ["Metric", "Channel", "Unit"]
    assert any(row[:3] == ["Mean", "R", "native code"] for row in content[1:])
    assert "7" in next(row for row in content[1:] if row[:2] == ["Mean", "R"])
    assert legacy_path.read_text(encoding="utf-8-sig") == legacy

    panel.statistics_view.setCurrentText("Raw")
    assert panel.table.item(0, 4).text() == "10"
    panel.shutdown()
    panel.close()


def test_pivot_reorders_sources_preserves_reference_key_and_invalidates_roi(qtbot: object) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.show()
    docs = [_document("같은이름.png", value) for value in (2, 7, 12, 20)]
    # In production W03 disambiguates same-name registered sources.
    for index, doc in enumerate(docs):
        doc.display_name = f"알고리즘 {index} / 같은이름.png"
    panel.set_documents(docs, None)
    _ready(panel, qtbot)
    panel.statistics_view.setCurrentText("Pivot")
    panel.pivot_reference.setCurrentIndex(3)
    previous = panel.pivot_reference.currentData()
    assert previous is not None
    assert panel.pivot_table.columnCount() == 6
    panel.set_documents(list(reversed(docs)), RoiBounds(1, 1, 4, 4), "Active ROI")
    assert panel.get_current_statistics_pivot() is None
    assert panel.pivot_table.rowCount() == 0
    assert not panel.pivot_export_button.isEnabled()
    _ready(panel, qtbot)
    pivot = panel.get_current_statistics_pivot()
    assert pivot is not None
    assert pivot.token.roi_ref == (1, 1, 4, 4)
    assert pivot.columns[0].alias.startswith("알고리즘 3")
    assert panel.pivot_reference.currentData() == previous
    assert (
        panel.pivot_table.item(_row(panel, "Mean · R"), 2).toolTip().find("Native samples: 16") >= 0
    )
    panel.shutdown()
    panel.close()


def test_six_source_horizontal_scroll_metric_filter_generation_and_gc(
    qtbot: object, tmp_path: Path
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.show()
    docs = [
        _document(f"아주긴한글소스별칭_{index}_{'검증' * 10}.png", index + 1) for index in range(6)
    ]
    panel.set_documents(docs, None)
    _ready(panel, qtbot)
    panel.statistics_view.setCurrentText("Pivot")
    assert panel.pivot_table.columnCount() == 8
    assert panel.pivot_table.horizontalHeader().sectionSize(7) >= 200
    panel.pivot_metrics.setCurrentText("All metrics")
    assert panel.pivot_table.rowCount() == 21
    panel.pivot_channel.setCurrentText("G")
    assert panel.pivot_table.rowCount() == 7
    panel.pivot_metrics.setCurrentText("Percentiles")
    assert panel.pivot_table.rowCount() == 3

    # Generation changed without analysis: old Pivot must not be exported.
    original = docs[0].generation
    docs[0].generation = original + 1
    assert panel.get_current_statistics_pivot() is None
    try:
        panel.export_pivot_csv(tmp_path / "stale.csv")
    except ValueError:
        pass
    else:
        raise AssertionError("stale Pivot export was allowed")
    assert not (tmp_path / "stale.csv").exists()
    panel.clear()
    assert panel.pivot_table.rowCount() == 0
    panel.shutdown()
    panel.close()
    del panel
    gc.collect()


def test_gray_uint16_native_pivot_and_delta(qtbot: object) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.show()
    docs = [
        ImageDocument.from_array(
            np.full((8, 8), value, dtype=np.uint16),
            f"gray-{index}.raw",
            bit_depth=12,
        )
        for index, value in enumerate((1000, 1005))
    ]
    panel.set_documents(docs, None)
    _ready(panel, qtbot)
    panel.statistics_view.setCurrentText("Pivot")
    assert panel.pivot_table.rowCount() == 3
    assert panel.pivot_table.item(0, 0).text() == "Mean · Gray"
    panel.pivot_reference.setCurrentIndex(1)
    panel.pivot_delta.setCurrentText("Absolute Δ")
    value_item = panel.pivot_table.item(0, 3)
    assert "Δ 5 native code" in value_item.text()
    assert "Effective bits: 12" in panel.pivot_table.horizontalHeaderItem(2).toolTip()
    panel.shutdown()
    panel.close()


def test_difference_metric_native_and_normalized_unit_columns(qtbot: object) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = ImageDocument.from_array(np.full((8, 8), 100, dtype=np.uint8), "a.png", bit_depth=8)
    second = ImageDocument.from_array(np.full((8, 8), 120, dtype=np.uint8), "b.png", bit_depth=8)
    panel.set_documents([first, second], (first.document_id, second.document_id))
    panel.calculate_difference()
    qtbot.waitUntil(lambda: panel.last_result is not None, timeout=3000)  # type: ignore[attr-defined]
    assert panel.metrics.columnCount() == 3
    assert panel.metrics.item(0, 1).text() == "20"
    assert panel.metrics.item(0, 2).text() == "native code"
    assert panel.metrics.item(1, 2).text() == "native code²"
    assert panel.metrics.item(3, 2).text() == "dB"
    assert panel.metrics.item(7, 2).text() == "ratio [0,1]"
    panel.shutdown()
    panel.close()

    normalized = DifferencePanel()
    qtbot.addWidget(normalized)  # type: ignore[attr-defined]
    low = ImageDocument.from_array(np.full((8, 8), 100, dtype=np.uint8), "low.png", bit_depth=8)
    high = ImageDocument.from_array(
        np.full((8, 8), 1000, dtype=np.uint16), "high.raw", bit_depth=10
    )
    normalized.set_documents([low, high], (low.document_id, high.document_id))
    normalized.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: normalized.last_result is not None, timeout=3000
    )
    assert normalized.metrics.item(0, 2).text() == "normalized [0,1]"
    assert normalized.metrics.item(1, 2).text() == "normalized²"
    assert normalized.metrics.item(3, 2).text() == "dB"
    normalized.shutdown()
    normalized.close()


def test_same_size_different_roi_coordinates_republish_native_statistics(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.show()
    gray = np.arange(64, dtype=np.uint8).reshape(8, 8)
    source = np.stack((gray, gray, gray), axis=-1)
    doc = ImageDocument.from_array(source, "gradient.png")
    first_roi = RoiBounds(0, 0, 2, 2)
    second_roi = RoiBounds(3, 3, 2, 2)
    panel.set_documents([doc], first_roi, "Active ROI")
    _ready(panel, qtbot)
    first = panel.get_current_statistics_pivot()
    assert first is not None and first.token.roi_ref == (0, 0, 2, 2)
    first_mean = next(row for row in first.rows if row.metric == "Mean" and row.channel == "R")
    assert first_mean.cells[0].sample_count == 4

    panel.set_documents([doc], second_roi, "Active ROI")
    assert panel.get_current_statistics_pivot() is None
    _ready(panel, qtbot)
    second = panel.get_current_statistics_pivot()
    assert second is not None and second.token.roi_ref == (3, 3, 2, 2)
    second_mean = next(row for row in second.rows if row.metric == "Mean" and row.channel == "R")
    assert second_mean.cells[0].sample_count == 4
    assert second_mean.cells[0].value != first_mean.cells[0].value
    panel.shutdown()
    panel.close()


@pytest.mark.parametrize("source_count", (2, 4, 6))
def test_pivot_copy_respects_exact_columns_and_sparse_ranges(
    qtbot: object, source_count: int
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.show()
    documents = [
        _document(f"원본_{index}_동일패턴.png", (index + 1) * 10)
        for index in range(source_count)
    ]
    panel.set_documents(documents, None)
    _ready(panel, qtbot)
    panel.statistics_view.setCurrentText("Pivot")
    panel.pivot_reference.setCurrentIndex(1)
    panel.pivot_delta.setCurrentText("Absolute Δ")
    table = panel.pivot_table
    mean_r = _row(panel, "Mean · R")
    source_col = 3  # second source; first two columns are Metric and Unit

    def copy(*rectangles: tuple[int, int, int, int]) -> str:
        table.clearSelection()
        for top, left, bottom, right in rectangles:
            table.setRangeSelected(
                QTableWidgetSelectionRange(top, left, bottom, right), True
            )
        panel.copy_selection()
        return QApplication.clipboard().text()

    # No source values or hidden channels may be added to metadata-only copies.
    assert copy((mean_r, 0, mean_r, 0)) == "Metric\nMean · R"
    assert copy((mean_r, 1, mean_r, 1)) == "Unit\nnative code"
    assert copy((mean_r, 0, mean_r, 1)) == "Metric\tUnit\nMean · R\tnative code"

    source_header = table.horizontalHeaderItem(source_col).text()
    single = copy((mean_r, source_col, mean_r, source_col))
    assert single == f"{source_header}\n20 | Delta 10 native code"
    assert single.count("\t") == 0
    assert "원본_2" not in single

    # Noncontiguous ranges retain only selected columns, preserve coordinates,
    # and leave unselected cell intersections empty rather than exporting data.
    sparse = copy((mean_r, 0, mean_r, 0), (mean_r + 1, source_col, mean_r + 1, source_col))
    assert sparse == (
        f"Metric\t{source_header}\n"
        "Mean · R\t\n"
        "\t20 | Delta 10 native code"
    )
    assert sparse.splitlines()[0].count("\t") == 1
    # Multiple separated source columns are not silently filled in.
    multi = copy(
        (mean_r, 2, mean_r, 2),
        (mean_r + 1, source_col, mean_r + 1, source_col),
    )
    source_a_header = table.horizontalHeaderItem(2).text()
    assert multi == (
        f"{source_a_header}\t{source_header}\n"
        "10 | Delta 0 native code\t\n"
        "\t20 | Delta 10 native code"
    )

    panel.shutdown()
    panel.close()


def test_difference_normalized_units_survive_clear_roi_invalid_and_recompute(
    qtbot: object,
) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    low = ImageDocument.from_array(
        np.full((8, 8), 100, dtype=np.uint8), "low.png", bit_depth=8
    )
    high = ImageDocument.from_array(
        np.full((8, 8), 1000, dtype=np.uint16), "high.raw", bit_depth=10
    )
    panel.set_documents([low, high], (low.document_id, high.document_id))
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None, timeout=3000
    )
    assert panel.metrics.item(0, 2).text() == "normalized [0,1]"
    assert panel.metrics.item(1, 2).text() == "normalized²"

    # A new valid ROI invalidates the metric without changing the domain.
    panel.set_active_roi(RoiBounds(1, 1, 4, 4))
    assert panel.last_result is None
    assert panel.metrics.item(0, 1).text() == "—"
    assert panel.metrics.item(0, 2).text() == "normalized [0,1]"
    assert panel.metrics.item(1, 2).text() == "normalized²"
    assert "Pending/unavailable" in panel.metrics.item(0, 2).toolTip()

    # Off-image ROI is not calculable, but must not be labelled native.
    panel.set_active_roi(RoiBounds(20, 20, 4, 4))
    assert not panel.calculate.isEnabled()
    assert panel.metrics.item(0, 1).text() == "—"
    assert panel.metrics.item(0, 2).text() == "normalized [0,1]"

    panel.set_active_roi(RoiBounds(1, 1, 4, 4))
    assert panel.calculate.isEnabled()
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None, timeout=3000
    )
    assert panel.metrics.item(0, 1).text() != "—"
    assert panel.metrics.item(0, 2).text() == "normalized [0,1]"
    assert panel.metrics.item(1, 2).text() == "normalized²"

    # Unknown/incompatible pair: do not invent a numeric-domain unit.
    rgb = ImageDocument.from_array(
        np.full((8, 8, 3), 10, dtype=np.uint8), "rgb.png"
    )
    panel.set_documents([low, rgb], (low.document_id, rgb.document_id))
    assert panel.metrics.item(0, 1).text() == "—"
    assert panel.metrics.item(0, 2).text() == "—"
    assert panel.metrics.item(1, 2).text() == "—"
    assert not panel.calculate.isEnabled()
    panel.shutdown()
    panel.close()
