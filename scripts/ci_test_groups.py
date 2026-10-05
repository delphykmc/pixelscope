"""Small durable pytest groups used by change-driven CI.

Feature PRs may run additional focused tests locally. Promotion into this registry is
explicit so a path classifier cannot silently grow an expensive catch-all suite.
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
            "Installed local/context Help availability and lifecycle.",
        ),
    ),
    "release": (
        DurableTest(
            "tests/unit/test_release_packaging.py",
            "Release artifact shape and packaging rules.",
        ),
        DurableTest(
            "tests/unit/test_release_bundle.py",
            "Release bundle completeness and integrity.",
        ),
        DurableTest(
            "tests/unit/test_release_candidate.py",
            "Release-candidate provenance and staging rules.",
        ),
    ),
    "raw": (
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
        DurableTest(
            "tests/ui/test_p1c_raw_dialog.py",
            "User-visible RAW profile and packed-stream controls.",
        ),
        DurableTest(
            "tests/ui/test_wp_b_raw_binary_compatibility.py",
            "RAW binary/profile UI compatibility and stride ownership.",
        ),
    ),
    "yuv": (
        DurableTest(
            "tests/unit/test_yuv_runtime_contracts.py",
            "Native YUV geometry and runtime boundaries.",
        ),
        DurableTest(
            "tests/unit/test_yuv_semantics.py",
            "Native plane, preview and analysis semantics.",
        ),
        DurableTest(
            "tests/ui/test_wp_c1_yuv_semantics.py",
            "User-visible native Y/U/V analysis semantics.",
        ),
        DurableTest(
            "tests/ui/test_wp_c2_yuv_difference.py",
            "Native YUV Difference and legacy-family compatibility.",
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
