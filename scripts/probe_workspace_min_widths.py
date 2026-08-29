from __future__ import annotations

import argparse

import numpy as np
from PySide6.QtCore import QSettings, QTimer, Qt

from pixelscope.app.application import create_application
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening


def _non_negative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Open an isolated PixelScope window for interactive Files/Image/IQA "
            "minimum-width experiments. The production layout contract is unchanged."
        )
    )
    parser.add_argument("--files-min", type=_non_negative, default=0)
    parser.add_argument("--image-min", type=_non_negative, default=0)
    parser.add_argument("--iqa-min", type=_non_negative, default=0)
    parser.add_argument("--files-width", type=_non_negative)
    parser.add_argument("--iqa-width", type=_non_negative)
    parser.add_argument("--window-width", type=_non_negative, default=1680)
    parser.add_argument("--window-height", type=_non_negative, default=980)
    parser.add_argument(
        "--with-sample-image",
        action="store_true",
        help="populate a synthetic image instead of leaving the Image workspace empty",
    )
    parser.add_argument(
        "--hide-iqa",
        action="store_true",
        help="start with IQA hidden",
    )
    return parser


def _sample_document() -> ImageDocument:
    height, width = 360, 640
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
    red = np.broadcast_to(x, (height, width))
    green = np.broadcast_to(y, (height, width))
    blue = ((red.astype(np.uint16) + green.astype(np.uint16)) // 2).astype(np.uint8)
    pixels = np.stack((red, green, blue), axis=-1)
    return ImageDocument.from_array(pixels, "layout_probe.png")


def _describe(label: str, widget: object) -> None:
    minimum_width = widget.minimumWidth()
    minimum_hint = widget.minimumSizeHint().width()
    size_hint = widget.sizeHint().width()
    print(
        f"{label:>6}: minimumWidth={minimum_width:4d}  "
        f"minimumSizeHint={minimum_hint:4d}  sizeHint={size_hint:4d}"
    )


def _apply_initial_widths(window: MainWindow, files_width: int | None, iqa_width: int | None) -> None:
    if files_width is not None:
        sizes = window.main_splitter.sizes()
        total = sum(sizes)
        if total > 0:
            target = min(files_width, total)
            window.main_splitter.setSizes([target, max(0, total - target)])
    if iqa_width is not None and window.iqa_dock.isVisible() and not window.iqa_dock.isFloating():
        window.resizeDocks([window.iqa_dock], [iqa_width], Qt.Orientation.Horizontal)


def main() -> int:
    args = _parser().parse_args()

    app = create_application([])
    # Keep the probe isolated from the normal PixelScope QSettings namespace.
    app.setOrganizationName("PixelScopeLayoutProbe")
    app.setApplicationName("PixelScopeLayoutProbe")
    QSettings().clear()

    window = MainWindow()
    install_beta_workspace_hardening(window)

    files = window.main_splitter.widget(0)
    image = window.presentation_panel
    iqa = window.iqa_workspace

    files.setMinimumWidth(args.files_min)
    image.setMinimumWidth(args.image_min)
    iqa.setMinimumWidth(args.iqa_min)

    if args.with_sample_image:
        window.add_document(_sample_document())
        window.set_layout_mode("Single View")

    window.resize(args.window_width, args.window_height)
    window.show()

    if not args.hide_iqa:
        window.iqa_workspace_action.setChecked(True)
        window._toggle_iqa()

    QTimer.singleShot(
        0,
        lambda: _apply_initial_widths(window, args.files_width, args.iqa_width),
    )

    print("Configured minimum widths")
    print(f" Files={args.files_min}  Image={args.image_min}  IQA={args.iqa_min}")
    print("Effective Qt hints after Beta hardening + probe override")
    _describe("Files", files)
    _describe("Image", image)
    _describe("IQA", iqa)
    print(
        "Splitter collapse policy: "
        f"Files={window.main_splitter.isCollapsible(0)}, "
        f"Image={window.main_splitter.isCollapsible(1)}"
    )
    print("Drag the Files splitter and IQA dock divider; live widths are shown in the title bar.")

    def update_title() -> None:
        if window.iqa_dock.isFloating():
            iqa_text = "float"
        elif window.iqa_dock.isVisible():
            iqa_text = str(window.iqa_dock.width())
        else:
            iqa_text = "hidden"
        window.setWindowTitle(
            "PixelScope Layout Probe | "
            f"Files {files.width()} | Image {image.width()} | IQA {iqa_text}"
        )

    timer = QTimer(window)
    timer.timeout.connect(update_title)  # type: ignore[attr-defined]
    timer.start(100)
    update_title()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
