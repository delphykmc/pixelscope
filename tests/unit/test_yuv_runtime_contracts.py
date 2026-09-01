from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pixelscope.core.comparison_set import Session, SessionSource
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.yuv_profile import YuvProfile


def _raw_profile() -> RawProfile:
    return RawProfile(
        name="legacy-raw",
        width=4,
        height=2,
        stride_bytes=8,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=0,
        white_level=4095,
    )


def _yuv_profile() -> YuvProfile:
    return YuvProfile(
        name="native-yuv",
        width=4,
        height=4,
        channel_layout="YUV420",
    )


@pytest.mark.parametrize(
    ("profile", "profile_type"),
    ((_raw_profile(), RawProfile), (_yuv_profile(), YuvProfile)),
)
def test_session_v1_repository_round_trips_raw_and_yuv_profiles(
    tmp_path: Path,
    profile: RawProfile | YuvProfile,
    profile_type: type[RawProfile] | type[YuvProfile],
) -> None:
    source = tmp_path / "source.bin"
    session = Session(
        registered_sources=(SessionSource(str(source), profile.dict()),),
    )
    target = tmp_path / "session.pixelscope"
    repository = ComparisonSetRepository()

    repository.save(target, session)
    restored = repository.load(target)

    payload = restored.registered_sources[0].raw_profile
    assert payload is not None
    assert isinstance(profile_type.parse_obj(payload), profile_type)
    assert payload["channel_layout"] == profile.channel_layout


def test_native_frame_rejects_odd_yuv422_width() -> None:
    with pytest.raises(ValueError, match="YUV422 width must be even"):
        NativeYuvFrame(
            y=np.zeros((2, 3), dtype=np.uint8),
            u=np.zeros((2, 1), dtype=np.uint8),
            v=np.zeros((2, 1), dtype=np.uint8),
            layout="YUV422",
        )


def test_native_frame_rejects_odd_yuv420_geometry() -> None:
    with pytest.raises(ValueError, match="YUV420 width must be even"):
        NativeYuvFrame(
            y=np.zeros((4, 3), dtype=np.uint8),
            u=np.zeros((2, 1), dtype=np.uint8),
            v=np.zeros((2, 1), dtype=np.uint8),
            layout="YUV420",
        )

    with pytest.raises(ValueError, match="YUV420 height must be even"):
        NativeYuvFrame(
            y=np.zeros((3, 4), dtype=np.uint8),
            u=np.zeros((1, 2), dtype=np.uint8),
            v=np.zeros((1, 2), dtype=np.uint8),
            layout="YUV420",
        )
