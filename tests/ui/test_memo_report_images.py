import cv2
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog
from test_memo_evidence import windows as memo_windows

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.io.memo_archive import load_memo_archive
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.ui.memo_report_images import annotate_memo_crop

windows = memo_windows
pytestmark = pytest.mark.usefixtures("isolated_qsettings")


@pytest.mark.parametrize("channels", [1, 3])
def test_report_image_has_unicode_filename_coordinates_and_unchanged_crop(qapp, channels):
    shape = (31, 43) if channels == 1 else (31, 43, 3)
    pixels = np.random.default_rng(12).integers(0, 256, shape, dtype=np.uint8)
    ok, png = cv2.imencode(".png", pixels)
    assert ok
    name = "비교 원본.png"
    coordinates = "x=2  y=3  width=43  height=31"
    result = annotate_memo_crop(png.tobytes(), name, coordinates)
    image = QImage.fromData(result)
    assert image.text("Source") == name and image.text("ROI") == coordinates
    decoded = cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR)
    expected = cv2.cvtColor(pixels, cv2.COLOR_GRAY2BGR) if channels == 1 else pixels
    left = (320 - 43) // 2
    np.testing.assert_array_equal(decoded[:31, left : left + 43], expected)
    assert decoded.shape[:2] == (31 + 84, 320)
    assert len(np.unique(decoded[31:].reshape(-1, 3), axis=0)) > 2  # Visible footer text.


def test_passive_memo_rectangles_do_not_change_analysis_roi_or_fit_range(qtbot):
    viewer = ImageViewer()
    qtbot.addWidget(viewer)
    viewer.resize(600, 480)
    viewer.show()
    viewer.set_document(ImageDocument.from_array(np.zeros((80, 120), np.uint8), "image"))
    qtbot.waitUntil(lambda: not viewer._geometry_timer.isActive())
    selected = RoiBounds(2, 3, 20, 15)
    viewer.set_roi_bounds(selected)
    before = viewer.view_box.viewRange()
    viewer.set_memo_regions(
        (("ROI 1 · sharpness", selected, True), ("ROI 2", RoiBounds(60, 40, 8, 9), False))
    )
    assert viewer.current_roi_bounds() == selected
    assert viewer.view_box.viewRange() == before
    for rectangle, label in viewer._memo_items:
        assert rectangle.acceptedMouseButtons() == Qt.MouseButton.NoButton
        assert label.acceptedMouseButtons() == Qt.MouseButton.NoButton
    viewer.set_memo_regions(())
    assert not viewer._memo_items and viewer.current_roi_bounds() == selected
    viewer.shutdown()
    viewer.shutdown()


@pytest.mark.parametrize("failure", ["folder", "renderer"])
def test_default_save_suggestion_and_atomic_folder_failure_retry(
    qtbot, monkeypatch, tmp_path, request, failure
):
    create = request.getfixturevalue("windows")
    source = tmp_path / "reference.png"
    assert cv2.imwrite(str(source), np.full((72, 96, 3), 80, np.uint8))
    window, memo = create()
    memo.show()
    window.open_image_paths([source])
    qtbot.waitUntil(
        lambda: window.viewer.document is not None
        and window.viewer.document.loading_state == "ready"
        and not window.viewer._geometry_timer.isActive(),
        timeout=10000,
    )
    assert window._shared_roi_changed(RoiBounds(2, 3, 16, 12))
    qtbot.waitUntil(lambda: memo._capture_worker is None, timeout=10000)
    target = tmp_path / "notes" / "notes.pxmemo"
    report = target.parent
    if failure == "folder":
        report.mkdir()
        (report / "user.txt").write_text("keep my file")
    else:
        from pixelscope.ui import review_window_integration as module

        original_render = module.annotate_memo_crop

        def fail_render(*_args):
            raise RuntimeError("simulated rendering failure")

        monkeypatch.setattr(module, "annotate_memo_crop", fail_render)
    chosen = []

    def choose(*args):
        chosen.append(args[2])
        return str(target), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    assert chosen[0].startswith("Memo_reference_") and chosen[0].endswith(".pxmemo")
    assert "failed" in memo.panel.status.text()
    assert not target.exists() and memo.library.path is None and memo.library.dirty
    if failure == "folder":
        assert (report / "user.txt").read_text() == "keep my file"
        (report / "user.txt").unlink()
        report.rmdir()
    else:
        monkeypatch.setattr(module, "annotate_memo_crop", original_render)
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    _, revision = load_memo_archive(target)
    assert memo.library.revision == revision and not memo.library.dirty
    memo.panel.note_edit.setPlainText("Another edit")
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    archive, new_revision = load_memo_archive(target)
    assert memo.library.revision == new_revision != revision
    assert archive.review.findings[0].note == "Another edit"
    assert len(chosen) == 2  # A failed initial save never attaches a destination.
    window.close()


def test_legacy_zip_save_creates_folder_without_replacing_legacy_file(
    qtbot, monkeypatch, tmp_path, request
):
    from pixelscope.io.memo_archive import MemoArchive, save_memo_archive

    window, memo = request.getfixturevalue("windows")()
    source = tmp_path / "source.png"
    assert cv2.imwrite(str(source), np.full((48, 64, 3), 90, np.uint8))
    window.open_image_paths([source])
    qtbot.waitUntil(
        lambda: window.viewer.document is not None
        and window.viewer.document.loading_state == "ready"
        and not window.viewer._geometry_timer.isActive(),
        timeout=10000,
    )
    window._shared_roi_changed(RoiBounds(2, 3, 12, 10))
    qtbot.waitUntil(lambda: memo._capture_worker is None, timeout=10000)
    legacy = tmp_path / "legacy.pxmemo"
    save_memo_archive(legacy, MemoArchive(memo.library.document, memo._crops))
    original = legacy.read_bytes()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a: (str(legacy), ""))
    memo.open_dialog()
    qtbot.waitUntil(
        lambda: memo._io_worker is None and memo.restore.phase == "applied", timeout=15000
    )
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    assert memo.library.path == tmp_path / "legacy" / "legacy.pxmemo"
    assert memo.library.path.is_file() and not memo.library.dirty
    assert legacy.read_bytes() == original
    assert not memo.library.path.read_bytes().startswith(b"PK")
    window.close()
