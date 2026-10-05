"""Define and profile the full-copy validation fixture policy.

Root-local generated environments and artifacts are excluded without hiding
tracked repository content in similarly named nested directories. Cache names
that are inherently generated remain excluded at any depth. The same policy is
used by the profiler and screenshot-rendering integration fixture.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath

ROOT_COPY_IGNORE_NAMES = frozenset(
    {
        ".git",
        ".venv",
        ".venv-release",
        ".tox",
        ".codex",
        ".test-results",
        "build",
        "dist",
        "release",
        "site",
        "temp",
    }
)
TREE_COPY_IGNORE_NAMES = frozenset(
    {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        ".cache",
    }
)


def copy_policy_ignores(relative: PurePosixPath) -> bool:
    """Return whether a repository-relative entry is excluded from the copy."""
    return relative.name in TREE_COPY_IGNORE_NAMES or (
        len(relative.parts) == 1 and relative.name in ROOT_COPY_IGNORE_NAMES
    )


def copytree_ignore(root: Path) -> Callable[[str, list[str]], list[str]]:
    """Build a ``shutil.copytree`` ignore callback for the shared copy policy."""
    root = root.resolve()

    def ignore(directory: str, names: list[str]) -> list[str]:
        relative_dir = Path(directory).resolve().relative_to(root)
        ignored = []
        for name in names:
            relative = PurePosixPath((relative_dir / name).as_posix())
            if copy_policy_ignores(relative):
                ignored.append(name)
        return ignored

    return ignore


def iter_copy_candidates(root: Path) -> Iterable[Path]:
    """Yield relative files that match the screenshot fixture copy contract."""
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        directory = Path(dirpath)
        relative_dir = directory.relative_to(root)
        dirnames[:] = [
            name
            for name in dirnames
            if not copy_policy_ignores(PurePosixPath((relative_dir / name).as_posix()))
        ]
        for filename in filenames:
            relative = relative_dir / filename
            if copy_policy_ignores(PurePosixPath(relative.as_posix())):
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


def tracked_paths_hidden_by_copy_policy(tracked: Iterable[str]) -> list[str]:
    """Return tracked paths hidden by an excluded ancestor or filename."""
    hidden = []
    for path in tracked:
        relative = PurePosixPath(path.replace("\\", "/"))
        prefixes = [PurePosixPath(*relative.parts[:index]) for index in range(1, len(relative.parts) + 1)]
        if any(copy_policy_ignores(prefix) for prefix in prefixes):
            hidden.append(path)
    return sorted(hidden)


def summarize_tree(root: Path, tracked: set[str] | None = None) -> dict[str, object]:
    """Summarize copy candidates by top-level path and Git tracking state."""
    root = root.resolve()
    tracked = tracked_paths(root) if tracked is None else tracked
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    non_tracked_rows: list[dict[str, object]] = []
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
        else:
            non_tracked_rows.append({"path": normalized, "bytes": size})
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
    non_tracked_rows.sort(key=lambda row: (-int(row["bytes"]), str(row["path"])))

    return {
        "root": str(root),
        "files": file_count,
        "bytes": byte_count,
        "tracked_files": tracked_count,
        "tracked_bytes": tracked_bytes,
        "non_tracked_files": file_count - tracked_count,
        "non_tracked_bytes": byte_count - tracked_bytes,
        "top_level": rows,
        "largest_non_tracked": non_tracked_rows[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print("PIXELSCOPE_E8_TREE " + json.dumps(summarize_tree(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
