"""Small durable pytest groups used by shared CI.

Feature PRs may run additional temporary focused tests, but those tests do not enter
this registry automatically. Promotion into a durable group requires an explicit
contract rationale and should keep the group intentionally small.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class DurableTest:
    node: str
    rationale: str


DURABLE_TEST_GROUPS: dict[str, tuple[DurableTest, ...]] = {
    "help": (
        DurableTest(
            "tests/ui/test_user_guide_help.py",
            "Local/context Help availability and lifecycle are durable installed-app contracts.",
        ),
    ),
    "release": (
        DurableTest(
            "tests/unit/test_release_packaging.py",
            "Release artifact shape and canonical packaging rules are durable contracts.",
        ),
        DurableTest(
            "tests/unit/test_release_candidate.py",
            "Release-candidate provenance and staging rules are durable contracts.",
        ),
    ),
    "raw": (
        DurableTest(
            "tests/unit/test_raw_reader.py",
            "Canonical unpacked and MIPI RAW decode/file-size behavior.",
        ),
        DurableTest(
            "tests/unit/test_packed_raw_stream.py",
            "Canonical generic packed-stream decode, bit-order and file-size behavior.",
        ),
        DurableTest(
            "tests/unit/test_wp_b_raw_profile_compatibility.py"
            "::test_minimum_stride_uses_storage_specific_row_layout",
            "Storage-specific minimum-row geometry shared by RAW profile handling.",
        ),
        DurableTest(
            "tests/ui/test_p1c_raw_dialog.py"
            "::test_raw_dialog_packed_stream_supports_variable_depth_and_bit_order",
            "Packed-stream controls and inferred stride are the user-visible RAW input contract.",
        ),
        DurableTest(
            "tests/ui/test_wp_b_raw_binary_compatibility.py"
            "::test_raw_dialog_tracks_minimum_stride_until_manual_override",
            "Auto-stride must stop owning the value after explicit user override.",
        ),
    ),
    "yuv": (
        DurableTest(
            "tests/unit/test_yuv_runtime_contracts.py::test_native_frame_rejects_odd_yuv422_width",
            "YUV422 geometry is a native decode boundary.",
        ),
        DurableTest(
            "tests/unit/test_yuv_runtime_contracts.py::test_native_frame_rejects_odd_yuv420_geometry",
            "YUV420 geometry is a native decode boundary.",
        ),
        DurableTest(
            "tests/unit/test_yuv_semantics.py::test_decode_native_planes_and_uv_deinterleave",
            "Native Y/U/V plane decoding and deinterleave are core semantics.",
        ),
        DurableTest(
            "tests/unit/test_yuv_semantics.py::test_bt601_full_preview_is_presentation_only",
            "RGB preview must not replace native YUV numerical authority.",
        ),
        DurableTest(
            "tests/unit/test_yuv_semantics.py"
            "::test_statistics_and_histogram_use_native_sample_cardinality",
            "Analysis sample cardinality must follow native plane geometry.",
        ),
        DurableTest(
            "tests/unit/test_yuv_semantics.py::test_profile_geometry_and_file_size_are_strict",
            "YUV profile geometry and stored file size are strict input contracts.",
        ),
        DurableTest(
            "tests/unit/test_yuv_semantics.py::test_rgb_gray_and_bayer_document_semantics_are_unchanged",
            "YUV support must not regress existing document families.",
        ),
        DurableTest(
            "tests/ui/test_wp_c1_yuv_semantics.py"
            "::test_yuv_statistics_histogram_and_line_controls_use_y_u_v",
            "User-visible analysis controls must expose native Y/U/V channels.",
        ),
        DurableTest(
            "tests/ui/test_wp_c2_yuv_difference.py"
            "::test_native_yuv_difference_uses_selected_plane_and_native_sample_count",
            "Difference must use selected native YUV plane semantics.",
        ),
        DurableTest(
            "tests/ui/test_wp_c2_yuv_difference.py"
            "::test_legacy_gray_rgb_bayer_and_normalized_compatibility_is_preserved",
            "YUV Difference must preserve legacy family compatibility.",
        ),
    ),
}


def nodes(group: str) -> list[str]:
    try:
        return [test.node for test in DURABLE_TEST_GROUPS[group]]
    except KeyError as exc:
        raise ValueError(f"unknown durable CI test group: {group}") from exc


def run_group(group: str) -> int:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *nodes(group)],
        check=False,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=sorted(DURABLE_TEST_GROUPS))
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        for test in DURABLE_TEST_GROUPS[args.group]:
            print(f"{test.node}\t{test.rationale}")
        return 0
    return run_group(args.group)


if __name__ == "__main__":
    raise SystemExit(main())
