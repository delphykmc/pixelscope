"""Classify changed paths into durable CI validation responsibilities.

This selector is intentionally Qt-free and stdlib-only. It decides which focused
validation groups are relevant; it does not execute tests or make merge decisions.
Unknown Python changes still receive cheap static validation, while native Windows
work is reserved for explicitly owned Help, release, RAW, or YUV paths.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-fA-F]{40}")
ZERO_SHA = "0" * 40


@dataclass(frozen=True)
class ChangedPath:
    path: str
    old_path: str | None = None

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.old_path, self.path) if self.old_path is not None else (self.path,)


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[:500]
        raise ValueError(f"Git command failed ({args[0]}): {detail}")
    return result.stdout


def _safe_path(raw: bytes) -> str:
    value = raw.decode("utf-8")
    if (
        not value
        or "\\" in value
        or value.startswith("/")
        or any(part in (".", "..") for part in value.split("/"))
        or "\x00" in value
    ):
        raise ValueError("unsafe path in Git diff")
    return value


def git_changed_paths(root: Path, base: str, head: str) -> list[ChangedPath]:
    raw = _git(
        root,
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        "--no-ext-diff",
        base,
        head,
    )
    if not raw:
        return []
    if not raw.endswith(b"\x00"):
        raise ValueError("truncated Git diff output")
    values = raw[:-1].split(b"\x00")
    changes: list[ChangedPath] = []
    offset = 0
    while offset < len(values):
        status = values[offset].decode("ascii")
        if not status or status[0] not in "AMDRCT":
            raise ValueError(f"unsupported Git diff status: {status!r}")
        if status.startswith(("R", "C")):
            if offset + 2 >= len(values):
                raise ValueError("truncated Git rename/copy entry")
            changes.append(ChangedPath(_safe_path(values[offset + 2]), _safe_path(values[offset + 1])))
            offset += 3
        else:
            if offset + 1 >= len(values):
                raise ValueError("truncated Git diff entry")
            changes.append(ChangedPath(_safe_path(values[offset + 1])))
            offset += 2
    return changes


def _matches(path: str, *, exact: tuple[str, ...] = (), prefixes: tuple[str, ...] = ()) -> bool:
    return path in exact or any(path.startswith(prefix) for prefix in prefixes)


DOC_EXACT = (
    "mkdocs.yml",
    "requirements/docs.txt",
    "scripts/check_docs.py",
    "scripts/check_screenshot_manifest.py",
    "scripts/user_guide_screenshot_hook.py",
    "scripts/audit_ui_screenshot_coverage.py",
    "scripts/verify_ui_screenshot_capture_packet.py",
    "scripts/audit_ui_screenshot_git_history.py",
    "scripts/select_ui_screenshots.py",
    "scripts/compare_ui_screenshots.py",
    "scripts/run_ui_screenshot_diff.py",
    "scripts/probe_ui_screenshot_environment.py",
    "scripts/screenshot_fixture_identity.py",
    "scripts/run_ui_capture_poc.py",
    "scripts/capture_ui_scene.py",
    "scripts/capture_ui_review.py",
    "scripts/check_user_guide_site.py",
    "scripts/build_user_guide.py",
    "scripts/check_user_guide_build_offline.py",
    "scripts/e8_profile.py",
    "scripts/preflight_ui_screenshot_diff.py",
    "scripts/skip_duplicate_user_guide_push.py",
    "scripts/prepare_user_guide_publication.py",
    "scripts/search_user_guide.py",
    "scripts/validate_user_guide_publication_ref.py",
    ".github/workflows/user-guide.yml",
    ".github/workflows/user-guide-publication.yml",
    ".github/workflows/ui-screenshot-diff.yml",
    ".github/workflows/ui-screenshot-poc.yml",
    ".github/pull_request_template.md",
)

HELP_EXACT = (
    "src/pixelscope/ui/user_guide_help.py",
    "tests/ui/test_user_guide_help.py",
)

RELEASE_PREFIXES = ("packaging/",)
RELEASE_EXACT = (
    "scripts/build_release_candidate.py",
    "scripts/build_release.py",
    "scripts/build_portable_release.py",
    "scripts/build_installer_release.py",
    "scripts/validate_release_artifact.py",
    "scripts/validate_release_bundle.py",
    "scripts/prepare_release_publication.py",
    "scripts/smoke_installer_release.py",
    "scripts/smoke_packaged_release.py",
    "scripts/smoke_portable_release.py",
    "scripts/release_candidate_contract.py",
    "scripts/release_contract.py",
    "tests/unit/test_release_packaging.py",
    "tests/unit/test_release_candidate.py",
    "tests/unit/test_release_candidate_provenance.py",
    "tests/unit/test_release_distribution.py",
    "tests/unit/test_release_publication.py",
)

RAW_PREFIXES = (
    "src/pixelscope/io/raw",
    "src/pixelscope/app/raw",
    "src/pixelscope/ui/raw",
)
RAW_TEST_PREFIXES = (
    "tests/unit/test_raw",
    "tests/unit/test_packed_raw",
    "tests/unit/test_wp_b_raw",
    "tests/ui/test_raw",
    "tests/ui/test_p1c_raw",
    "tests/ui/test_p3b_raw",
    "tests/ui/test_wp_b_raw",
    "tests/integration/test_p3b_raw",
    "tests/integration/test_raw",
)

YUV_PREFIXES = (
    "src/pixelscope/io/yuv",
    "src/pixelscope/app/yuv",
    "src/pixelscope/ui/yuv",
)
YUV_TEST_PREFIXES = (
    "tests/unit/test_yuv",
    "tests/ui/test_wp_c1_yuv",
    "tests/ui/test_wp_c2_yuv",
)

SHARED_RUNTIME = ("requirements/runtime.txt", "pyproject.toml")


def classify_paths(changes: list[ChangedPath]) -> dict[str, bool]:
    paths = {path for change in changes for path in change.paths}
    docs = any(
        _matches(path, exact=DOC_EXACT, prefixes=("docs/", "examples/")) for path in paths
    )
    help_ui = any(path in HELP_EXACT for path in paths)
    release = any(
        _matches(path, exact=RELEASE_EXACT, prefixes=RELEASE_PREFIXES) for path in paths
    )
    raw = any(path.startswith(RAW_PREFIXES + RAW_TEST_PREFIXES) for path in paths)
    yuv = any(path.startswith(YUV_PREFIXES + YUV_TEST_PREFIXES) for path in paths)
    shared_runtime = any(path in SHARED_RUNTIME for path in paths)
    if shared_runtime:
        help_ui = release = raw = yuv = True

    static = any(path.endswith(".py") for path in paths)
    src_changed = any(path.startswith("src/") and path.endswith(".py") for path in paths)
    windows_native = help_ui or release or raw or yuv
    any_validation = docs or static or windows_native

    return {
        "docs": docs,
        "help_ui": help_ui,
        "release": release,
        "raw": raw,
        "yuv": yuv,
        "static": static,
        "src_changed": src_changed,
        "windows_native": windows_native,
        "any_validation": any_validation,
    }


def _resolve(root: Path, value: str) -> str:
    if SHA.fullmatch(value) is None:
        raise ValueError("base/head must be explicit 40-character commit SHAs")
    resolved = _git(root, "rev-parse", "--verify", f"{value}^{{commit}}").decode().strip()
    if resolved.lower() != value.lower():
        raise ValueError("commit identity did not resolve to requested SHA")
    return resolved


def _resolve_base(root: Path, base: str, head: str) -> str:
    if base != ZERO_SHA:
        return _resolve(root, base)
    merge_base = _git(root, "merge-base", "origin/main", head).decode().strip()
    return _resolve(root, merge_base)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        head = _resolve(root, args.head)
        base = _resolve_base(root, args.base, head)
        changes = git_changed_paths(root, base, head)
        groups = classify_paths(changes)
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"CI change classification failed: {exc}", file=sys.stderr)
        return 1

    report = {
        "schema_version": 1,
        "base_sha": base,
        "head_sha": head,
        "changed_paths": [
            {"path": change.path, "old_path": change.old_path} for change in changes
        ],
        "groups": groups,
    }
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            for key, value in groups.items():
                handle.write(f"{key}={str(value).lower()}\n")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
