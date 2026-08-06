from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Literal, cast

from pixelscope.app.application import create_application
from pixelscope.io.raw_format import ContainerDType, StorageFormat, minimum_row_bytes
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
        "--format",
        choices=("unpacked", "mipi_raw10", "mipi_raw12", "mipi_raw14"),
        default="unpacked",
        dest="storage_format",
        help="Initial RAW storage format.",
    )
    parser.add_argument(
        "--alignment",
        choices=("lsb", "msb"),
        default="lsb",
        help="Bit alignment used for the unpacked preview profile.",
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


def _profile(layout: str, storage_format: str, alignment: str) -> RawProfile:
    is_bayer = layout == "BAYER"
    fixed_depth = {
        "mipi_raw10": 10,
        "mipi_raw12": 12,
        "mipi_raw14": 14,
    }.get(storage_format)
    bit_depth = fixed_depth or 10
    packed = storage_format != "unpacked"
    format_key = cast(StorageFormat, storage_format)
    container_dtype: ContainerDType | None = None if packed else "uint16"
    stride = minimum_row_bytes(
        3840,
        format_key,
        container_dtype,
    )
    return RawProfile(
        name="preview",
        width=3840,
        height=2160,
        stride_bytes=stride,
        offset_bytes=0,
        storage_format=format_key,
        container_dtype=container_dtype,
        endianness=None if packed else "little",
        bit_depth=bit_depth,
        bit_alignment=None if packed else alignment,
        channel_layout=layout,
        bayer_pattern="RGGB" if is_bayer else None,
        black_level=(64, 64, 64, 64) if is_bayer else 64,
        white_level=(1 << bit_depth) - 1,
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
    profile = _profile(args.layout, args.storage_format, args.alignment)

    with tempfile.TemporaryDirectory(prefix="pixelscope-raw-preview-") as directory:
        raw_path = Path(directory) / "preview.raw"
        expected = (
            profile.offset_bytes
            + (profile.height - 1) * profile.stride_bytes
            + profile.minimum_row_bytes
        )
        with raw_path.open("wb") as raw_file:
            raw_file.truncate(_source_size(expected, args.state))

        dialog = RawOpenDialog()
        dialog.setFixedWidth(args.width)
        dialog.set_profile(profile)
        dialog.set_source_path(raw_path)
        dialog.set_json_confirmation_option_visible(not args.hide_json_option)
        dialog.show()
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
