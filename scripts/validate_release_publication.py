from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.publication_contract import (  # noqa: E402
    release_tag,
    validate_publication,
    validate_release_tag,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate provider-neutral PixelScope release publication staging"
    )
    parser.add_argument(
        "--require-tag",
        action="store_true",
        help="also require the local canonical release tag to resolve to source_commit",
    )
    args = parser.parse_args()

    metadata = validate_publication()
    if args.require_tag:
        source_commit = metadata.get("source_commit")
        if not isinstance(source_commit, str) or not source_commit:
            raise RuntimeError("publication metadata source_commit is invalid")
        validate_release_tag(source_commit)
        print(f"Release tag validation PASS: {release_tag()} -> {source_commit}")

    print("PixelScope release publication validation PASS.")
    print("No GitHub Release, upload, tag creation, signing, or privileged action was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
