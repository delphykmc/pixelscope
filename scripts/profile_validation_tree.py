"""Profile the repository tree that full-copy validation fixtures can see.

This is diagnostic tooling for Issue #113. It does not change validation
behavior. The explicit ignore names mirror the screenshot-rendering fixture's
``shutil.copytree`` exclusions so owner-local measurements can distinguish
tracked repository content from extra local files that are still copied.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

COPY_IGNORE_NAMES = frozenset(
    {
        ".git",
        ".venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        ".cache",
        "build",
        "dist",
        "site",
        "temp",
    }
)


def iter_copy_candidates(root: Path) -> Iterable[Path]:
    """Yield relative files that match the screenshot fixture copy contract."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in COPY_IGNORE_NAMES for part in relative.parts):
            continue
        yield relative


def tracked_paths(root: Path) -> set[str]:
    """Return Git-tracked paths as normalized repository-relative strings."""
    process = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {name for name in process.stdout.split("\0") if name}


def summarize_tree(root: Path, tracked: set[str] | None = None) -> dict[str, object]:
    """Summarize copy candidates by top-level path and Git tracking state."""
    root = root.resolve()
    tracked = tracked_paths(root) if tracked is None else tracked
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    file_count = 0
    byte_count = 0
    tracked_count = 0
    tracked_bytes = 0

    for relative in iter_copy_candidates(root):
        size = (root / relative).stat().st_size
        normalized = relative.as_posix()
        is_tracked = normalized in tracked
        top_level = relative.parts[0]
        bucket = totals[top_level]
        bucket[0] += 1
        bucket[1] += size
        if is_tracked:
            bucket[2] += 1
            bucket[3] += size
            tracked_count += 1
            tracked_bytes += size
        file_count += 1
        byte_count += size

    rows = []
    for name, values in totals.items():
        files, bytes_, tracked_files, tracked_bytes_ = values
        rows.append(
            {
                "path": name,
                "files": files,
                "bytes": bytes_,
                "tracked_files": tracked_files,
                "tracked_bytes": tracked_bytes_,
                "non_tracked_files": files - tracked_files,
                "non_tracked_bytes": bytes_ - tracked_bytes_,
            }
        )
    rows.sort(key=lambda row: (-int(row["bytes"]), str(row["path"])))

    return {
        "root": str(root),
        "files": file_count,
        "bytes": byte_count,
        "tracked_files": tracked_count,
        "tracked_bytes": tracked_bytes,
        "non_tracked_files": file_count - tracked_count,
        "non_tracked_bytes": byte_count - tracked_bytes,
        "top_level": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print("PIXELSCOPE_E8_TREE " + json.dumps(summarize_tree(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
