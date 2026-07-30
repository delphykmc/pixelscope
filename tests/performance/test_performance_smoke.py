from __future__ import annotations

from pathlib import Path
from time import perf_counter

import numpy as np

from pixelscope.core.diff_engine import absolute_difference, signed_difference
from pixelscope.core.display_transform import DisplayTransform, to_display_uint8
from pixelscope.core.statistics import histogram
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw


def test_4096x3072_uint16_smoke(tmp_path: Path) -> None:
    shape = (3072, 4096)
    source = np.arange(shape[0] * shape[1], dtype=np.uint16).reshape(shape)
    raw_path = tmp_path / "large.raw"
    source.tofile(raw_path)
    profile = RawProfile(
        name="large",
        width=shape[1],
        height=shape[0],
        stride_bytes=shape[1] * 2,
        dtype="uint16",
        endianness="little",
        bit_depth=16,
        packing="unpacked_u16",
        channel_layout="GRAY",
        black_level=0,
        white_level=65535,
    )

    timings: dict[str, float] = {}
    start = perf_counter()
    mapped = read_raw(raw_path, profile)
    timings["memmap"] = perf_counter() - start
    start = perf_counter()
    preview = to_display_uint8(mapped, DisplayTransform(0, 65535))
    timings["preview"] = perf_counter() - start
    start = perf_counter()
    result = histogram(mapped, 1024)
    timings["histogram"] = perf_counter() - start
    start = perf_counter()
    signed = signed_difference(mapped, source)
    timings["signed_difference"] = perf_counter() - start
    start = perf_counter()
    absolute = absolute_difference(mapped, source)
    timings["absolute_difference"] = perf_counter() - start

    print(
        "performance_seconds=",
        timings,
        "temporary_bytes=",
        {
            "preview": preview.nbytes,
            "signed": signed.nbytes,
            "absolute": absolute.nbytes,
        },
    )
    assert result.counts[0].sum() == source.size
    assert preview.shape == shape
    assert not np.any(signed)
    assert not np.any(absolute)
