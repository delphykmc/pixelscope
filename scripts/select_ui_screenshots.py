"""WP-Help-E3: conservative, Qt-free screenshot impact selection for a pinned Git pair.

This script selects scenes for a *future* E4 capture job. It does not capture,
compare, approve or replace guide PNGs. Unknown rendering-relevant source paths
fail open to all manifest IDs, never to an empty selection.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = "docs/user-guide/assets/screenshots/manifest.json"
ASSET_DIR = "docs/user-guide/assets/screenshots/"
GUIDE_DIR = "docs/user-guide/"
MARKER = re.compile(r"<!--\s*pixelscope:screenshot\s+([a-z0-9-]+)\s*-->")
SCREENSHOT_IMAGE = re.compile(r"!\[[^]\n]*\]\(([^)\n]+)\)")
SHA = re.compile(r"[0-9a-fA-F]{40}")
STATUS = re.compile(r"(?:[AMDT]|[RC][0-9]{1,3})")
FALLBACK_DIRS = (
    "src/pixelscope/",
    "src/pixelscope/ui/",
    "src/pixelscope/app/",
    "src/pixelscope/core/",
    "src/pixelscope/io/",
    "src/pixelscope/remote/",
    "src/pixelscope/workers/",
    "src/pixelscope/assets/",
)
CAPTURE_HELPER = re.compile(r"scripts/(?:capture|run_ui_capture|generate_).*\.py$")


@dataclass(frozen=True)
class ChangedFile:
    status: str
    path: str
    old_path: str | None = None

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.old_path, self.path) if self.old_path is not None else (self.path,)


def _path(raw: bytes) -> str:
    value = raw.decode("utf-8")
    if (
        not value
        or "\\" in value
        or value.startswith("/")
        or any(part in (".", "..") for part in value.split("/"))
        or "\x00" in value
    ):
        raise ValueError("unsafe path in Git name-status result")
    return value


def parse_name_status_z(payload: bytes) -> list[ChangedFile]:
    """Parse Git's -z format without splitting filenames on spaces, tabs or newlines."""
    if not payload:
        return []
    if not payload.endswith(b"\x00"):
        raise ValueError("truncated Git name-status -z output")
    values = payload[:-1].split(b"\x00")
    results: list[ChangedFile] = []
    offset = 0
    while offset < len(values):
        kind = values[offset].decode("ascii")
        if STATUS.fullmatch(kind) is None:
            raise ValueError(f"unsupported Git diff status: {kind!r}")
        count = 3 if kind.startswith(("R", "C")) else 2
        if offset + count > len(values):
            raise ValueError("truncated Git rename/copy entry")
        if count == 3:
            results.append(ChangedFile(kind, _path(values[offset + 2]), _path(values[offset + 1])))
        else:
            results.append(ChangedFile(kind, _path(values[offset + 1])))
        offset += count
    return results


def _git(root: Path, *args: str) -> bytes:
    command = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if command.returncode:
        detail = command.stderr.decode("utf-8", errors="replace").strip()[:500]
        raise ValueError(f"Git command failed ({args[0]}): {detail}")
    return command.stdout


def resolve_sha(root: Path, value: str) -> str:
    """Require and verify immutable full commit SHAs, not moving branch names."""
    if SHA.fullmatch(value) is None:
        raise ValueError("base/head must be explicit 40-character commit SHAs")
    resolved = _git(root, "rev-parse", "--verify", f"{value}^{{commit}}").decode().strip()
    if resolved.lower() != value.lower():
        raise ValueError("commit identity did not resolve to the requested SHA")
    return resolved


def git_changed_files(root: Path, base: str, head: str) -> list[ChangedFile]:
    raw = _git(root, "diff", "--name-status", "-z", "--find-renames", "--no-ext-diff", base, head)
    return parse_name_status_z(raw)


def _git_text(root: Path, revision: str, path: str) -> str:
    """Read a pinned blob; only a genuinely absent page may count as empty.

    Treat object/database/read failures as selection failures, not a docs-only
    change. A renamed or deleted Markdown page is legitimately missing on one
    side of a pinned comparison.
    """
    command = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{path}"],
        capture_output=True,
        check=False,
    )
    if command.returncode:
        names = _git(root, "ls-tree", "-z", "--full-tree", "--name-only", revision, "--", path)
        if path.encode("utf-8") not in names.split(b"\x00"):
            return ""
        raise ValueError(f"Git show failed for present path: {path}")
    return command.stdout.decode("utf-8")


def _glob(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _screenshots(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest["screenshots"]
    ids = [row["id"] for row in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate Screenshot ID; run check_docs.py")
    return {row["id"]: row for row in entries}


def screenshot_references(text: str) -> set[str]:
    """Image/marker references only, not unrelated prose in the same topic page."""
    found = set(MARKER.findall(text))
    for match in SCREENSHOT_IMAGE.finditer(text):
        target = match.group(1).split(maxsplit=1)[0].split("?", 1)[0].split("#", 1)[0]
        if "assets/screenshots/" in target:
            found.add(Path(target).name.removesuffix(".png"))
    return found


def screenshot_markup(text: str) -> tuple[str, ...]:
    """Preserve reference syntax and alt/target changes, unlike just the ID set."""
    found = ["marker:" + m.group() for m in MARKER.finditer(text)]
    found += [
        "image:" + m.group()
        for m in SCREENSHOT_IMAGE.finditer(text)
        if "assets/screenshots/" in m.group(1)
    ]
    return tuple(sorted(found))


def _tag_impact(
    per_id: dict[str, set[str]],
    grouped: set[str],
    for_path: set[str],
    ids: set[str],
    reason: str,
) -> None:
    """Attribute a reason only to affected IDs, also recording path evidence."""
    for key in ids:
        per_id[key].add(reason)
    grouped.add(reason)
    for_path.add(reason)


def select_changes(
    changed: list[ChangedFile],
    base_manifest: dict[str, Any],
    head_manifest: dict[str, Any],
    *,
    base_sha: str,
    head_sha: str,
    read_at_revision: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    """Return an inspectable report. Each rename checks both old and new paths."""
    old = _screenshots(base_manifest)
    new = _screenshots(head_manifest)
    all_ids = set(old) | set(new)
    removed_ids = sorted(set(old) - set(new))
    target_profile_changed = base_manifest.get("target_capture_profile") != head_manifest.get(
        "target_capture_profile"
    )
    # Changes to screenshot meaning/placement require human review even when
    # no PNG was committed (e.g. a scene-contract or approval metadata edit).
    review_fields = (
        "scenario",
        "capture_mode",
        "status",
        "approved",
        "filename",
        "placement",
        "viewport",
        "pages",
        "alt",
        "legacy_output",
    )
    manifest_review_ids = sorted(
        key
        for key in all_ids
        if old.get(key) != new.get(key)
        and (
            key not in old
            or key not in new
            or any(old[key].get(field) != new[key].get(field) for field in review_fields)
        )
    )
    shared = head_manifest.get("shared_source_globs", [])
    if not shared or head_manifest.get("impact_ownership_status") != "complete":
        raise ValueError("E3 needs complete manifest ownership and shared_source_globs")
    for row in new.values():
        if not row.get("source_globs"):
            raise ValueError(f"missing E3 source ownership: {row['id']}")
    selected_reasons: dict[str, set[str]] = defaultdict(set)
    warnings: set[str] = set()
    paths: list[dict[str, Any]] = []
    png_changes: list[dict[str, str]] = []

    for change in changed:
        # A rename/copy contains two independently meaningful paths. Record
        # screenshot-specific evidence separately from the path-level summary:
        # a fallback on one side must not claim that *all* IDs own the other.
        per_id_reasons: dict[str, set[str]] = defaultdict(set)
        reasons: set[str] = set()

        for path in change.paths:
            path_reasons: set[str] = set()

            if path == MANIFEST_PATH:
                old_header = {
                    key: value for key, value in base_manifest.items() if key != "screenshots"
                }
                new_header = {
                    key: value for key, value in head_manifest.items() if key != "screenshots"
                }
                if old_header != new_header:
                    _tag_impact(
                        per_id_reasons,
                        reasons,
                        path_reasons,
                        all_ids,
                        "manifest-shared-contract",
                    )
                for key in all_ids:
                    if old.get(key) != new.get(key):
                        _tag_impact(
                            per_id_reasons,
                            reasons,
                            path_reasons,
                            {key},
                            "manifest-scene-contract",
                        )
                if not path_reasons:
                    reasons.add("manifest-format-only")
                continue
            if path.startswith(ASSET_DIR) and path.endswith(".png"):
                key = path[len(ASSET_DIR) : -4]
                if "/" in key or key not in all_ids:
                    _tag_impact(
                        per_id_reasons,
                        reasons,
                        path_reasons,
                        all_ids,
                        "unmapped-screenshot-asset",
                    )
                    warnings.add(f"unmapped-screenshot-asset: {path}")
                else:
                    _tag_impact(
                        per_id_reasons,
                        reasons,
                        path_reasons,
                        {key},
                        "committed-screenshot-png",
                    )
                png_changes.append({"path": path, "status": change.status, "screenshot_id": key})
                continue
            if path in (
                ".github/workflows/ui-screenshot-poc.yml",
                "scripts/select_ui_screenshots.py",
                "scripts/check_screenshot_manifest.py",
            ):
                _tag_impact(
                    per_id_reasons,
                    reasons,
                    path_reasons,
                    all_ids,
                    "screenshot-automation-contract",
                )
                continue
            if path == ASSET_DIR + "README.md":
                _tag_impact(
                    per_id_reasons,
                    reasons,
                    path_reasons,
                    all_ids,
                    "screenshot-readme-reference",
                )
                continue
            if _glob(path, shared):
                _tag_impact(
                    per_id_reasons,
                    reasons,
                    path_reasons,
                    all_ids,
                    "shared-rendering-or-capture-dependency",
                )
                continue
            head_owners = {
                key for key, record in new.items() if _glob(path, record.get("source_globs", []))
            }
            for key in head_owners:
                _tag_impact(per_id_reasons, reasons, path_reasons, {key}, "feature-owner:" + key)
            # Ownership can change in the same PR as code. Preserve base-side
            # ownership for every ID, not only IDs removed from the manifest.
            for key, record in old.items():
                if key not in head_owners and _glob(path, record.get("source_globs", [])):
                    label = "removed-feature-owner:" if key not in new else "base-feature-owner:"
                    _tag_impact(per_id_reasons, reasons, path_reasons, {key}, label + key)
            if path.startswith(GUIDE_DIR) and path.endswith(".md"):
                if read_at_revision is None:
                    # The caller may omit a revision reader in unit/embedding
                    # contexts. The fallback still respects both page graphs.
                    page = path.removeprefix(GUIDE_DIR)
                    page_owners = {
                        key for key, row in old.items() if page in row.get("pages", [])
                    } | {key for key, row in new.items() if page in row.get("pages", [])}
                    if page_owners:
                        _tag_impact(
                            per_id_reasons,
                            reasons,
                            path_reasons,
                            page_owners,
                            "screenshot-markdown-page",
                        )
                else:
                    old_text = read_at_revision(base_sha, path)
                    new_text = read_at_revision(head_sha, path)
                    previous = screenshot_references(old_text)
                    current = screenshot_references(new_text)
                    if previous != current or screenshot_markup(old_text) != screenshot_markup(
                        new_text
                    ):
                        refs = previous | current
                        _tag_impact(
                            per_id_reasons,
                            reasons,
                            path_reasons,
                            refs & all_ids,
                            "screenshot-markdown-reference",
                        )
                        if refs - all_ids:
                            _tag_impact(
                                per_id_reasons,
                                reasons,
                                path_reasons,
                                all_ids,
                                "unmapped-screenshot-reference",
                            )
                            warnings.add(f"unmapped-screenshot-reference: {path}")
                if not path_reasons:
                    reasons.add("docs-prose-only")
                continue
            if (
                (path.startswith(FALLBACK_DIRS) or CAPTURE_HELPER.fullmatch(path))
                and not _glob(path, shared)
                and not any(
                    _glob(path, row.get("source_globs", []))
                    for row in list(old.values()) + list(new.values())
                )
            ):
                _tag_impact(
                    per_id_reasons,
                    reasons,
                    path_reasons,
                    all_ids,
                    "unmapped-ui-impact-full-capture",
                )
                warnings.add(f"unmapped-ui-impact: {path}")
            if not path_reasons:
                reasons.add("no-rendered-ui-impact")
        for key, own_reasons in per_id_reasons.items():
            selected_reasons[key].update(own_reasons)
        paths.append(
            {
                "status": change.status,
                "path": change.path,
                "old_path": change.old_path,
                "selected_ids": sorted(per_id_reasons),
                "reasons": sorted(reasons),
            }
        )

    screenshots = []
    capture_eligible_ids: list[str] = []
    capture_deferred: list[dict[str, str]] = []
    for key in sorted(selected_reasons):
        record = new.get(key, old.get(key, {}))
        present_in_head = key in new
        mode = record.get("capture_mode", "removed")
        eligible = present_in_head and mode == "isolated"
        if eligible:
            capture_eligible_ids.append(key)
        else:
            defer_reason = f"capture-mode:{mode}" if present_in_head else "removed-from-head"
            capture_deferred.append({"id": key, "reason": defer_reason})
        screenshots.append(
            {
                "id": key,
                "present_in_head": present_in_head,
                "capture_mode": mode,
                "status": record.get("status", "removed"),
                "capture_eligible": eligible,
                "reasons": sorted(selected_reasons[key]),
            }
        )
    return {
        "schema_version": 1,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed_paths": paths,
        "selected_ids": sorted(selected_reasons),
        "selected_screenshots": screenshots,
        "capture_eligible_ids": capture_eligible_ids,
        "capture_deferred": capture_deferred,
        "committed_png_changes": png_changes,
        "manifest_review_ids": manifest_review_ids,
        "removed_ids": removed_ids,
        "target_profile_changed": target_profile_changed,
        "requires_image_review": bool(png_changes or manifest_review_ids or target_profile_changed),
        "warnings": sorted(warnings),
        "no_selection_reason": (
            "no changed paths" if not changed else "no screenshot-affecting change detected"
        )
        if not screenshots
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Full pinned base commit SHA")
    parser.add_argument("--head", required=True, help="Full pinned head commit SHA")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, help="Write machine-readable JSON report")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        base = resolve_sha(root, args.base)
        head = resolve_sha(root, args.head)
        before = json.loads(_git_text(root, base, MANIFEST_PATH))
        after = json.loads(_git_text(root, head, MANIFEST_PATH))
        report = select_changes(
            git_changed_files(root, base, head),
            before,
            after,
            base_sha=base,
            head_sha=head,
            read_at_revision=lambda sha, path: _git_text(root, sha, path),
        )
    except (OSError, UnicodeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"E3 screenshot impact selection failed: {exc}", file=sys.stderr)
        return 1
    output = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
