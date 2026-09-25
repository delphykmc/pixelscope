"""Fail-closed E4 native-GUI cost gate for an already pinned E3 selection report.

Run after both immutable Git checkouts and stdlib E3 selection, but before
installing Qt/Pillow or starting a real GUI process. This does not change the
selector's conservative impact classification or approve screenshot bytes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

SHA = re.compile(r"[0-9a-fA-F]{40}")


def capture_required(selection: dict[str, Any], base_sha: str, head_sha: str) -> bool:
    """Only a complete, explicitly harmless selection can bypass native GUI."""
    if SHA.fullmatch(base_sha) is None or SHA.fullmatch(head_sha) is None:
        raise ValueError("E4 preflight requires immutable full base/head SHA")
    if selection.get("schema_version") != 1:
        raise ValueError("E4 preflight requires an E3 schema v1 report")
    if selection.get("base_sha") != base_sha or selection.get("head_sha") != head_sha:
        raise ValueError("E4 preflight selection belongs to a different pinned Git pair")
    selected = selection.get("selected_ids")
    if not isinstance(selected, list) or any(not isinstance(key, str) for key in selected):
        raise ValueError("E4 preflight requires an explicit selected ID list")
    warnings = selection.get("warnings")
    if not isinstance(warnings, list):
        raise ValueError("E4 preflight requires an explicit warning list")
    if selected:
        return True  # removed/deferred IDs still need E4's real review report
    for field in (
        "requires_image_review",
        "committed_png_changes",
        "manifest_review_ids",
        "removed_ids",
        "target_profile_changed",
    ):
        if selection.get(field):
            raise ValueError(f"E4 preflight cannot bypass native path: {field}")
    if warnings:
        raise ValueError("E4 preflight cannot bypass warnings with empty selection")
    if selection.get("no_selection_reason") not in (
        "no changed paths",
        "no screenshot-affecting change detected",
    ):
        raise ValueError("E4 preflight requires an explicit no-selection reason")
    return False


def write_no_selection_report(
    selection: dict[str, Any], output_dir: Path, base_sha: str, head_sha: str
) -> None:
    """Retain E4 artifact identity even when costly dependencies are skipped."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "selection": selection,
        "warnings": [],
        "screenshots": [],
        "status": "no affected screenshots",
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(
        "# WP-Help-E4 pinned Windows real-QWidget screenshot diff\n\n"
        f"- Base SHA: `{base_sha}`\n"
        f"- Head SHA: `{head_sha}`\n"
        "- Status: **no affected screenshots**\n"
        f"- E3 reason: {selection['no_selection_reason']}\n"
        "- Native GUI dependencies/captures skipped after pinned E3 selection.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        needed = capture_required(selection, args.base, args.head)
        if not needed:
            write_no_selection_report(selection, args.output_dir, args.base, args.head)
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with Path(output).open("a", encoding="utf-8") as handle:
                handle.write(f"capture_required={str(needed).lower()}\n")
        print(f"E4 pinned preflight: {'run native GUI' if needed else 'no affected screenshots'}")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"E4 preflight FAILED (fail-closed): {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
