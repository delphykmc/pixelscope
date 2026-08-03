from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from pixelscope.app.application import create_application
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.raw_open_dialog import RawOpenDialog


def review_document(index: int) -> ImageDocument:
    height, width = 360, 640
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
    red = np.broadcast_to((x.astype(np.uint16) + index * 23) % 256, (height, width))
    green = np.broadcast_to((y.astype(np.uint16) + index * 31) % 256, (height, width))
    blue = ((red.astype(np.uint16) + green.astype(np.uint16)) // 2 + index * 13) % 256
    pixels = np.stack((red, green, blue), axis=-1).astype(np.uint8)
    folder = f"camera_{index % 3 + 1}"
    name = f"isp_capture_{index + 1:02d}.png"
    return ImageDocument.from_array(
        pixels,
        name,
        source_path=Path("C:/PixelScope_Review") / folder / name,
    )


def grab(widget: QWidget, output: Path, wait_ms: int = 350) -> None:
    widget.show()
    QTest.qWait(120)
    if isinstance(widget, MainWindow):
        widget.fit_image()
    QTest.qWait(wait_ms)
    QThreadPool.globalInstance().waitForDone(5000)
    QTest.qWait(200)
    if not widget.grab().save(str(output)):
        raise RuntimeError(f"failed to save UI capture: {output}")


def populated_window(count: int, layout: str = "Auto") -> MainWindow:
    window = MainWindow()
    documents = [review_document(index) for index in range(count)]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode(layout)
    window.resize(1680, 980)
    window.bottom_dock.hide()
    return window


def save_window(window: MainWindow, output: Path, wait_ms: int = 350) -> None:
    grab(window, output, wait_ms)
    window.close()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/capture_ui_review.py OUTPUT_DIRECTORY")
    output = Path(sys.argv[1])
    if not output.is_dir():
        raise SystemExit(f"output directory does not exist: {output}")

    app = create_application([])
    app.setOrganizationName("PixelScopeCapture")
    QSettings().clear()

    empty = MainWindow()
    empty.resize(1680, 980)
    save_window(empty, output / "empty_state.png")

    save_window(populated_window(1, "Single View"), output / "single_image.png", 1200)
    save_window(populated_window(3, "Multi View"), output / "three_image_multiview.png")
    save_window(populated_window(5, "Multi View"), output / "five_image_multiview.png")
    save_window(populated_window(6, "Multi View"), output / "six_image_multiview.png")

    difference = populated_window(2, "Multi View")
    difference.analysis_tabs.setCurrentWidget(difference.difference_panel)
    difference.difference_panel.calculate_difference()
    save_window(difference, output / "difference_analysis.png", 1500)

    histogram = populated_window(3, "Multi View")
    histogram._show_bottom_results()
    histogram.bottom_tabs.setCurrentWidget(histogram.comparison_analysis_panel.histogram_panel)
    save_window(histogram, output / "histogram_docked.png", 1500)

    profile = populated_window(2, "Multi View")
    profile._shared_line_changed(LineSelection(40, 180, 580))
    profile.bottom_tabs.setCurrentWidget(profile.line_profile_panel)
    save_window(profile, output / "line_profile_docked.png", 1500)

    floating = populated_window(2, "Multi View")
    floating._show_bottom_results()
    floating.bottom_dock.setFloating(True)
    floating.bottom_dock.resize(1200, 520)
    grab(floating.bottom_dock, output / "plots_floating.png", 1500)
    floating.close()

    raw_dialog = RawOpenDialog()
    raw_dialog.set_profile(
        RawProfile(
            name="capture_profile",
            width=3840,
            height=2160,
            dtype="uint16",
            stride_bytes=7680,
            bit_depth=10,
            packing="unpacked_u16",
            channel_layout="BAYER",
            bayer_pattern="RGGB",
            black_level=(64, 64, 64, 64),
            white_level=1023,
        )
    )
    raw_dialog.resize(520, 620)
    grab(raw_dialog, output / "raw_profile_dialog.png")
    raw_dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
