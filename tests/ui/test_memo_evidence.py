"""Real Memo workflow: independent ROI evidence, native statistics and offline use."""
from __future__ import annotations

import csv
import io
import zipfile

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.roi import RoiBounds
from pixelscope.io.memo_archive import load_memo_archive

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


@pytest.fixture
def windows(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_kw: QMessageBox.StandardButton.Yes)

    def create():
        window = MainWindow()
        qtbot.addWidget(window)
        compose_main_window_presentation(window)
        window.resize(1400, 880)
        window.show()
        window.named_review_coordinator.show()
        opened.append(window)
        return window, window.named_review_coordinator

    yield create
    for window in opened:
        window.close()


def _idle(qtbot, memo):
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)


def test_multi_roi_crops_statistics_save_offline_reopen_and_report(
    qtbot,
    monkeypatch,
    tmp_path,
    windows,
):
    paths = []
    for index in range(2):
        path = tmp_path / f"image{index}.png"
        assert cv2.imwrite(str(path), np.full((72, 96, 3), (40, 70, 90 + index), np.uint8))
        paths.append(path)
    window, memo = windows()
    window.open_image_paths(paths)
    window.set_layout_mode("Multi View")
    qtbot.waitUntil(
        lambda: len(window.multi_compare_view.occupied_viewers) == 2
        and all(
            v.document is not None
            and v.document.loading_state == "ready"
            and v.measure_physical_zoom().valid
            and not v._geometry_timer.isActive()
            for v in window.multi_compare_view.occupied_viewers
        ),
        timeout=10000,
    )
    rois = (RoiBounds(2, 3, 16, 12), RoiBounds(27, 20, 20, 15), RoiBounds(55, 40, 18, 16))
    for index, roi in enumerate(rois):
        assert window._apply_shared_roi(roi, allow_channel_split=False)
        memo.panel.title_edit.setText(f"Defect {index + 1}")
        memo.panel.note_edit.setPlainText("Comparison note <script> is plain text")
        memo.panel.include_statistics.setChecked(index == 0)
        if index == 0:

            def statistics_ready():
                panel = window.comparison_analysis_panel
                token = panel.get_current_analysis_token()
                return (
                    token is not None
                    and token.roi_ref == (2, 3, 16, 12)
                    and (panel.get_presented_analysis_token() == token)
                )

            qtbot.waitUntil(statistics_ready, timeout=10000)
        memo.panel.add_button.click()
        qtbot.waitUntil(lambda: memo._capture_worker is None, timeout=15000)
        assert len(memo.library.document.findings) == index + 1, memo.panel.status.text()
    assert len(memo._crops) == 6
    assert memo.panel.crop_previews.count() == 2
    first = memo.library.document.findings[0]
    assert first.analysis[0].status == "captured"
    frozen = dict(memo._crops)
    memo.edit(first.id, "Edited note", "No pixels changed", ())
    assert memo._crops == frozen
    target = tmp_path / "inspection.pxmemo"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_kw: (str(target), ""))
    memo.save_dialog()
    _idle(qtbot, memo)
    assert target.is_file() and not memo.library.dirty, memo.panel.status.text()
    archive, _ = load_memo_archive(target)
    assert dict(archive.crops) == frozen
    window.close()

    for path in paths:
        path.unlink()
    fresh, offline = windows()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_kw: (str(target), ""))
    offline.open_dialog()
    _idle(qtbot, offline)
    assert len(offline.library.document.findings) == 3
    assert not fresh.documents
    assert offline.panel.crop_previews.count() == 2
    assert "unavailable" in offline.panel.status.text()
    offline.show()
    qtbot.waitUntil(lambda: offline.dock.isVisible())
    assert fresh.grab().save(str(tmp_path / "memo-offline.png"))
    for index in range(3):
        offline.panel.findings.setCurrentRow(index)
        assert offline.panel.crop_previews.count() == 2
    with zipfile.ZipFile(target) as saved:
        pngs = [n for n in saved.namelist() if n.endswith(".png")]
        assert len(pngs) == 6
        assert {saved.read(n) for n in pngs} == set(frozen.values())
        csvs = [n for n in saved.namelist() if n.endswith(".csv")]
        assert len(csvs) == 1
        rows = list(csv.DictReader(io.StringIO(saved.read(csvs[0]).decode("utf-8-sig"))))
    assert rows and all(int(r["Samples"]) == 192 for r in rows)
    assert all((r["X"], r["Y"], r["Width"], r["Height"]) == ("2", "3", "16", "12") for r in rows)
    means = [float(r["Value"]) for r in rows if r["Metric"].lower() == "mean"]
    assert sorted(means) == [40, 40, 70, 70, 90, 91]
    assert not fresh.documents  # saved evidence never requires an original

    # Delete one note, retain the other evidence, and save the same revision.
    offline.delete(offline.library.document.findings[1].id)
    assert len(offline._crops) == 4
    offline.save_dialog()
    _idle(qtbot, offline)
    assert len(load_memo_archive(target)[0].review.findings) == 2


def test_corrupt_open_retains_notebook_and_unsaved_memory_is_discardable(
    qtbot,
    monkeypatch,
    tmp_path,
    windows,
):
    window, memo = windows()
    document = memo.library.document
    broken = tmp_path / "broken.pxmemo"
    broken.write_bytes(b"not a ZIP")
    memo._start_io("open", broken)
    _idle(qtbot, memo)
    assert memo.library.document is document
    assert "failed" in memo.panel.status.text()
    memo.library.dirty = True
    assert window.close()
    assert window._closing and memo._closed


def test_missing_roi_does_not_create_memo(qtbot, windows):
    window, memo = windows()
    memo.panel.add_button.click()
    assert "Draw an ROI" in memo.panel.status.text()
    assert not memo.library.document.findings
    window.close()


def test_single_view_records_visible_image_when_several_sources_are_selected(
    qtbot,
    tmp_path,
    windows,
):
    paths = []
    for index in range(2):
        path = tmp_path / f"single{index}.png"
        assert cv2.imwrite(str(path), np.full((72, 96, 3), 40 + index, np.uint8))
        paths.append(path)
    window, memo = windows()
    window.open_image_paths(paths)
    window.set_layout_mode("Single View")
    qtbot.waitUntil(
        lambda: len(window.selected_documents) == 2
        and window.viewer.document is not None
        and window.viewer.document.loading_state == "ready"
        and window.viewer.measure_physical_zoom().valid
        and not window.viewer._geometry_timer.isActive(),
        timeout=10000,
    )
    assert window._apply_shared_roi(RoiBounds(2, 3, 16, 12), allow_channel_split=False)
    shown = window.viewer.document
    window._primary_page_slot = 1
    memo.add()
    qtbot.waitUntil(lambda: memo._capture_worker is None, timeout=15000)
    assert len(memo.library.document.findings) == 1, memo.panel.status.text()
    finding = memo.library.document.findings[0]
    assert len(finding.source_keys) == 1 and len(memo._crops) == 1
    assert memo.library.document.sources[0].locator.local_path == str(shown.source_path)
    assert len(window.selected_documents) == 2  # recording is not a selection change
    assert window._primary_page_slot == 1
    memo.panel.include_statistics.setChecked(True)
    memo.add()
    assert "Multi View" in memo.panel.status.text()
    assert len(memo.library.document.findings) == 1
