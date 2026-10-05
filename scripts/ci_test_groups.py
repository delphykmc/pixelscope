"""Small durable pytest groups with explicit executor ownership.

Hosted CI groups are deterministic and avoid Qt/widget lifecycle or geometry timing.
Owner/local UI groups remain executable from the same registry, but Windows owner/local
validation is authoritative for those contracts.
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


CI_TEST_GROUPS: dict[str, tuple[DurableTest, ...]] = {
    "release": (
        DurableTest(
            "tests/unit/test_release_packaging.py",
            "Release artifact shape and packaging rules.",
        ),
        DurableTest(
            "tests/unit/test_release_candidate.py",
            "Release bundle integrity, candidate provenance and staging rules.",
        ),
        DurableTest(
            "tests/unit/test_release_candidate_provenance.py",
            "Release candidate source identity and provenance contract.",
        ),
        DurableTest(
            "tests/unit/test_release_distribution.py",
            "Portable/installer distribution and third-party notice contract.",
        ),
        DurableTest(
            "tests/unit/test_release_publication.py",
            "Release publication staging, metadata and tag contract.",
        ),
    ),
    "raw-core": (
        DurableTest(
            "tests/unit/test_raw_reader.py",
            "Canonical unpacked and MIPI RAW decode/file-size behavior.",
        ),
        DurableTest(
            "tests/unit/test_packed_raw_stream.py",
            "Generic packed-stream decode, bit-order and file-size behavior.",
        ),
        DurableTest(
            "tests/unit/test_wp_b_raw_profile_compatibility.py",
            "RAW profile storage geometry and compatibility.",
        ),
    ),
    "yuv-core": (
        DurableTest(
            "tests/unit/test_yuv_runtime_contracts.py",
            "Native YUV geometry and runtime boundaries.",
        ),
        DurableTest(
            "tests/unit/test_yuv_semantics.py",
            "Native plane, preview and analysis semantics.",
        ),
    ),
}


OWNER_LOCAL_UI_TEST_GROUPS: dict[str, tuple[DurableTest, ...]] = {
    "help-ui": (
        DurableTest(
            "tests/ui/test_user_guide_help.py",
            "Installed local/context Help availability and Qt lifecycle.",
        ),
    ),
    "raw-ui": (
        DurableTest(
            "tests/ui/test_p1c_raw_dialog.py",
            "User-visible RAW profile and packed-stream controls.",
        ),
        DurableTest(
            "tests/ui/test_wp_b_raw_binary_compatibility.py",
            "RAW binary/profile UI compatibility and stride ownership.",
        ),
    ),
    "yuv-ui": (
        DurableTest(
            "tests/ui/test_wp_c1_yuv_semantics.py",
            "User-visible native Y/U/V analysis semantics.",
        ),
        DurableTest(
            "tests/ui/test_wp_c2_yuv_difference.py",
            "Native YUV Difference and legacy-family UI compatibility.",
        ),
    ),
}


DURABLE_TEST_GROUPS: dict[str, tuple[DurableTest, ...]] = {
    **CI_TEST_GROUPS,
    **OWNER_LOCAL_UI_TEST_GROUPS,
}


def nodes(group: str) -> list[str]:
    try:
        return [test.node for test in DURABLE_TEST_GROUPS[group]]
    except KeyError as exc:
        raise ValueError(f"unknown durable test group: {group}") from exc


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
