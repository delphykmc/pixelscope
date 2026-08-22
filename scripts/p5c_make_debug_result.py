from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pixelscope.remote.iqa_debug_fixture import DebugResultMode, write_debug_result_bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic schema-v2 result and logical P5-C replay JSON.",
    )
    parser.add_argument(
        "--storage-root",
        required=True,
        type=Path,
        help="Existing local path for the configured shared-storage root.",
    )
    parser.add_argument(
        "--storage-root-id",
        required=True,
        help="Logical Remote IQA storage_root_id used by client/server configuration.",
    )
    parser.add_argument(
        "--relative-path",
        required=True,
        help="Portable POSIX result directory path under the storage root.",
    )
    parser.add_argument(
        "--mode",
        choices=tuple(item.value for item in DebugResultMode),
        default=DebugResultMode.COMPLETE.value,
    )
    parser.add_argument("--job-id", default="job_debug_000001")
    parser.add_argument(
        "--submission-kind",
        choices=("current_pair", "folder_pair"),
        default="folder_pair",
    )
    parser.add_argument(
        "--replay-json",
        type=Path,
        default=None,
        help="Optional local replay JSON output path.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        bundle = write_debug_result_bundle(
            args.storage_root,
            args.storage_root_id,
            args.relative_path,
            mode=DebugResultMode(args.mode),
            job_id=args.job_id,
            submission_kind=args.submission_kind,
            replay_path=args.replay_json,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"P5-C debug result generation failed: {exc}", file=sys.stderr)
        return 2

    print(f"Result root: {bundle.result_root}")
    print(f"Replay JSON: {bundle.replay_path}")
    print(
        "Logical result reference: "
        f"{bundle.replay.result_reference.storage_root_id}:"
        f"{bundle.replay.result_reference.relative_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
