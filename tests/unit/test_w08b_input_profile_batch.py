from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.io.input_profile_batch import (
    ExistingProfileBinding,
    candidate_file_is_current,
    interpretation_key,
    preflight_input_profile_batch,
)
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import required_file_size
from pixelscope.io.yuv_profile import YuvProfile


def raw_profile(*, width: int = 4, height: int = 4, stride: int = 8) -> RawProfile:
    return RawProfile(
        name="batch", width=width, height=height, stride_bytes=stride,
        storage_format="unpacked", container_dtype="uint16", endianness="little",
        bit_depth=12, bit_alignment="lsb", channel_layout="GRAY",
        black_level=0, white_level=4095,
    )


def test_one_raw_profile_preflights_four_binary_sources(tmp_path: Path) -> None:
    profile = raw_profile()
    paths = tuple(tmp_path / f"sample_{i}{ext}" for i, ext in enumerate(
        (".raw", ".data", ".yuv", ".raw")
    ))
    for path in paths:
        path.write_bytes(bytes(required_file_size(profile)))
    result = preflight_input_profile_batch(paths, profile)
    assert [entry.status for entry in result] == ["eligible"] * 4
    assert len({entry.interpretation for entry in result}) == 1
    assert all(entry.revision is not None for entry in result)
    assert len(preflight_input_profile_batch((paths[0], paths[0]), profile)) == 1


def test_raw_trailing_bytes_exact_mode_and_min_last_row(tmp_path: Path) -> None:
    profile = raw_profile(height=3, stride=12)
    assert required_file_size(profile) == 32
    path = tmp_path / "frame.raw"
    path.write_bytes(bytes(35))
    eligible = preflight_input_profile_batch((path,), profile)[0]
    assert eligible.eligible
    assert "3 trailing bytes" in eligible.reason
    assert "offset 32" in eligible.reason
    strict = preflight_input_profile_batch(
        (path,), profile, require_exact_raw_size=True
    )[0]
    assert strict.status == "rejected"
    path.write_bytes(bytes(31))
    assert preflight_input_profile_batch((path,), profile)[0].status == "rejected"


@pytest.mark.parametrize("layout,bytes_required", (
    ("YUV444", 48), ("YUV422", 32), ("YUV420", 24),
))
def test_yuv_size_must_be_exact(
    tmp_path: Path, layout: str, bytes_required: int
) -> None:
    profile = YuvProfile(width=4, height=4, channel_layout=layout)
    path = tmp_path / "frame.yuv"
    assert profile.expected_file_size == bytes_required
    path.write_bytes(bytes(bytes_required))
    assert preflight_input_profile_batch((path,), profile)[0].eligible
    path.write_bytes(bytes(bytes_required + 1))
    trailing = preflight_input_profile_batch((path,), profile)[0]
    assert trailing.status == "rejected"
    assert "exactly" in trailing.reason
    path.write_bytes(bytes(bytes_required - 1))
    assert preflight_input_profile_batch((path,), profile)[0].status == "rejected"
    wrong_ext = tmp_path / "frame.data"
    wrong_ext.write_bytes(bytes(bytes_required))
    assert preflight_input_profile_batch((wrong_ext,), profile)[0].status == "rejected"


def test_sidecar_registration_and_explicit_override(
    tmp_path: Path,
) -> None:
    profile = raw_profile()
    changed = raw_profile(stride=10)
    path = tmp_path / "source.raw"
    path.write_bytes(bytes(60))
    (tmp_path / "source.json").write_text("{}", encoding="utf-8")
    binding = ExistingProfileBinding("doc-1", 7, changed)
    base = preflight_input_profile_batch((path,), profile, existing={path: binding})[0]
    assert base.status == "rejected"
    partial = preflight_input_profile_batch(
        (path,), profile, existing={path: binding}, override_registered=True
    )[0]
    assert partial.status == "rejected"
    approved = preflight_input_profile_batch(
        (path,), profile, existing={path: binding},
        override_registered=True, override_sidecars=True
    )[0]
    assert approved.eligible
    assert approved.document_id == "doc-1" and approved.generation == 7
    assert approved.previous_interpretation == interpretation_key(changed)
    assert candidate_file_is_current(approved)
    path.write_bytes(bytes(61))
    assert not candidate_file_is_current(approved)
    same = preflight_input_profile_batch(
        (path,), profile, existing={path: ExistingProfileBinding("doc-1", 7, profile)}
    )[0]
    assert same.status == "unchanged"


def test_missing_nonregular_unsupported_and_mixed_size_sources(tmp_path: Path) -> None:
    profile = raw_profile()
    matching = tmp_path / "ok.raw"
    short = tmp_path / "short.data"
    unsupported = tmp_path / "image.png"
    missing = tmp_path / "missing.yuv"
    directory = tmp_path / "directory.raw"
    directory.mkdir()
    matching.write_bytes(bytes(32))
    short.write_bytes(bytes(10))
    unsupported.write_bytes(bytes(32))
    entries = preflight_input_profile_batch(
        (matching, short, unsupported, missing, directory), profile
    )
    assert [item.status for item in entries] == [
        "eligible", "rejected", "rejected", "rejected", "rejected"
    ]
    assert all(not entry.eligible for entry in entries[1:])
