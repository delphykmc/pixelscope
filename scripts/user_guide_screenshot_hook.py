"""E5: insert manifest-owned real screenshot assets into canonical Markdown.

A missing *declared* PNG is an intentional omission, never a broken image link.
No capture, network, publication, provenance mutation or Qt import happens here.
The executable Qt-free manifest checker remains the authority for the source
marker/page graph and for every PNG which does exist.
"""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path
from typing import Any

from scripts.check_screenshot_manifest import find_problems

_MARKER = re.compile(r"<!-- pixelscope:screenshot ([a-z][a-z0-9-]*) -->")
_ASSETS = Path("assets/screenshots")
_MANIFEST = _ASSETS / "manifest.json"


def _root(config: Any) -> Path:
    return Path(config["docs_dir"]).resolve()


def _manifest(docs_root: Path) -> dict[str, dict[str, Any]]:
    source = json.loads((docs_root / _MANIFEST).read_text(encoding="utf-8"))
    return {row["id"]: row for row in source["screenshots"]}


def on_pre_build(config: Any) -> None:
    """Make direct `mkdocs build --strict` enforce the entire E5 contract."""
    docs_root = _root(config)
    problems = find_problems(docs_root.parents[1])
    if problems:
        raise ValueError("Screenshot manifest contract failed:\n - " + "\n - ".join(problems))


def on_page_markdown(markdown: str, *, page: Any, config: Any, files: Any) -> str:
    """Expand only validated ID markers; leave unrelated Markdown untouched."""
    docs_root = _root(config)
    source_page = page.file.src_path.replace("\\", "/")
    records = _manifest(docs_root)

    def insert(match: re.Match[str]) -> str:
        key = match.group(1)
        row = records.get(key)
        if row is None or row["placement"] != "required" or source_page not in row["pages"]:
            raise ValueError(f"{source_page}: invalid screenshot marker: {key}")
        image = docs_root / _ASSETS / row["filename"]
        if not image.is_file():
            return ""  # expected missing ID: no `img`, no remote fallback
        relative = posixpath.relpath(
            (_ASSETS / row["filename"]).as_posix(),
            posixpath.dirname(source_page) or ".",
        )
        alt = row["alt"].replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
        return f"![{alt}]({relative})"

    return _MARKER.sub(insert, markdown)
