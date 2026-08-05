from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Literal

from pixelscope.app.application import create_application
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.raw_open_dialog import RAW_DIALOG_WIDTH, RawOpenDialog


SizeState = Literal["match", "warning", "error"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open the RAW profile dialog without starting PixelScope.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=RAW_DIALOG_WIDTH,
        help="Dialog width in pixels.",
    )
    parser.add_argument(
        "--layout",
        choices=("BAYER", "GRAY"),
        default="BAYER",
        help="Initial pixel layout.",
    )
    parser.add_argument(
        "--state",
        choices=("match", "warning", "error"),
        default="match",
        help="File-size diagnostic state.",
    )
    parser.add_argument(
        "--hide-json-option",
        action="store_true",
        help="Hide the 'Don't show JSON profiles next time' option.",
    )
    return parser.parse_args()


def _profile(layout: str) -> RawProfile:
    is_bayer = layout == "BAYER"
    return RawProfile(
        name="preview",
        width=3840,
        height=2160,
        stride_bytes=7680,
        offset_bytes=0,
        dtype="uint16",
        endianness="little",
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout=layout,
        bayer_pattern="RGGB" if is_bayer else None,
        black_level=(64, 64, 64, 64) if is_bayer else 64,
        white_level=1023,
    )


def _source_size(expected: int, state: SizeState) -> int:
    if state == "warning":
        return expected + 128
    if state == "error":
        return max(0, expected - 128)
    return expected


def main() -> int:
    args = _parse_args()
    app = create_application()
    profile = _profile(args.layout)

    with tempfile.TemporaryDirectory(
        prefix="pixelscope-raw-preview-"
    ) as directory:
        raw_path = Path(directory) / "preview.raw"
        expected = (
            profile.offset_bytes
            + (profile.height - 1) * profile.stride_bytes
            + profile.width * 2
        )
        with raw_path.open("wb") as raw_file:
            raw_file.truncate(_source_size(expected, args.state))

        dialog = RawOpenDialog()
        dialog.setFixedWidth(args.width)
        dialog.set_profile(profile)
        dialog.set_source_path(raw_path)
        dialog.set_json_confirmation_option_visible(
            not args.hide_json_option
        )
        dialog.show()
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
