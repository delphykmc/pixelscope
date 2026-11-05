"""W07 UI contract: typed Pivot is read-only and legacy Raw export remains intact."""
from __future__ import annotations

import csv
import gc
from pathlib import Path

import numpy as np

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel


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
    from PySide6.QtWidgets import QApplication

    copied = QApplication.clipboard().text()
    assert "Mean\tR\tnative code" in copied
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
