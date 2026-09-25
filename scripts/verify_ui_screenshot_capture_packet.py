"""Verify original real-QWidget candidate sidecars against approved guide PNGs.

This is a read-only, Qt-free E6 pre-import/provenance gate. The original
owner-local packet must be supplied: re-capturing on a different Windows host
at the same source SHA does NOT preserve PNG-byte identity. Never stage,
rewrite, approve or auto-merge an image as a side effect of verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path
from typing import Any

if __package__:
    from .check_screenshot_manifest import find_problems, png_problems
else:
    from check_screenshot_manifest import find_problems, png_problems

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("docs/user-guide/assets/screenshots/manifest.json")
ASSETS = MANIFEST.parent
SOURCE_RE = re.compile(r"^[0-9a-f]{40}$")


def packet_problems(
    manifest: dict[str, Any], packet: Path, assets: Path
) -> list[str]:
    """Bind each exact capture-sidecar and PNG to an approved screenshot ID."""
    errors: list[str] = []
    rows = manifest["screenshots"]
    if not packet.is_dir() or packet.is_symlink():
        return ["original candidate packet is missing or is a symlink"]
    used: set[str] = set()
    for row in rows:
        key, scene = row["id"], row["scenario"]
        approved = row.get("approved")
        if row["status"] != "approved" or not isinstance(approved, dict):
            errors.append(f"{key}: approved manifest record required")
            continue
        # The public E1 packet uses scene-1.png/json; a local candidate packet
        # may use canonical id.png/json. Never combine two different versions.
        options = [scene + "-1", key]
        available = [stem for stem in options if (packet / (stem + ".png")).exists()]
        if len(available) != 1:
            errors.append(f"{key}: expected exactly one candidate PNG for scene/ID")
            continue
        stem = available[0]
        if stem in used:
            errors.append(f"{key}: original packet file reused by another ID")
            continue
        used.add(stem)
        image = packet / (stem + ".png")
        sidecar = packet / (stem + ".json")
        committed = assets / row["filename"]
        if image.is_symlink() or sidecar.is_symlink() or not sidecar.is_file():
            errors.append(f"{key}: candidate PNG and JSON sidecar must be real local files")
            continue
        if not committed.is_file() or committed.is_symlink():
            errors.append(f"{key}: approved committed PNG is absent or symlinked")
            continue
        errors.extend(f"{key}: {issue}" for issue in png_problems(image))
        try:
            observed = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            errors.append(f"{key}: invalid original JSON sidecar")
            continue
        if not isinstance(observed, dict):
            errors.append(f"{key}: sidecar must be an object")
            continue
        expected_sha = approved.get("image_sha256")
        candidate_sha = hashlib.sha256(image.read_bytes()).hexdigest()
        committed_sha = hashlib.sha256(committed.read_bytes()).hexdigest()
        if candidate_sha != expected_sha or committed_sha != expected_sha:
            errors.append(f"{key}: original candidate, committed PNG and approved hash differ")
        checks = {
            "status": "captured",
            "scenario": scene,
            "source_sha": approved.get("capture_source_sha"),
            "application_version": approved.get("application_version"),
            "capture_profile": approved.get("comparison_profile_id"),
            "image_sha256": expected_sha,
        }
        for field, expected in checks.items():
            if observed.get(field) != expected:
                errors.append(f"{key}: original sidecar {field} disagrees with manifest")
        if observed.get("callback_errors") or observed.get("error_type"):
            errors.append(f"{key}: sidecar records a GUI callback/capture failure")
        fixture = observed.get("fixture_sha256")
        if not isinstance(fixture, str) or not re.fullmatch("[0-9a-f]{64}", fixture):
            errors.append(f"{key}: missing original fixture identity")
        geometry = observed.get("geometry")
        if not isinstance(geometry, dict):
            errors.append(f"{key}: missing original QWidget geometry")
            continue
        try:
            pixels = list(struct.unpack_from(">II", image.read_bytes(), 16))
        except (OSError, struct.error):
            errors.append(f"{key}: original PNG dimensions unreadable")
            continue
        logical = geometry.get("logical_widget")
        if geometry.get("pixel_png") != pixels:
            errors.append(f"{key}: sidecar PNG dimensions disagree with image")
        if (
            not isinstance(logical, list)
            or len(logical) != 2
            or any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in logical)
        ):
            errors.append(f"{key}: invalid original logical widget geometry")
            continue
        if row.get("geometry_policy") == "fixed" and logical != [
            row["viewport"]["width"], row["viewport"]["height"]
        ]:
            errors.append(f"{key}: fixed-widget geometry differs from manifest")
    return errors


def source_history_problems(root: Path, manifest: dict[str, Any]) -> list[str]:
    """Ensure capture source is a real ancestor and runtime source did not drift."""
    errors: list[str] = []
    shas = {row.get("approved", {}).get("capture_source_sha") for row in manifest["screenshots"]}
    if len(shas) != 1:
        return ["different source SHAs require individual source-history checks"]
    source = shas.pop()
    if not isinstance(source, str) or not SOURCE_RE.fullmatch(source):
        return ["invalid capture source SHA"]
    for args, message in [
        (["cat-file", "-e", f"{source}^{{commit}}"], "capture source not in Git history"),
        (["merge-base", "--is-ancestor", source, "HEAD"], "capture source is not ancestor"),
    ]:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ["Git unavailable for source history verification"]
        if result.returncode:
            errors.append(message)
    # Staging/promotion may change documents and tests; it must not quietly
    # change app, builder, pinned runtime or UI between capture and promotion.
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", source, "HEAD", "--",
         "src", "scripts/capture_ui_scene.py", "scripts/capture_ui_review.py",
         "requirements/runtime.txt", "pyproject.toml"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode or result.stdout.strip():
        errors.append("runtime/real-UI source changed after candidate capture")
    return errors


def verify(root: Path, packet: Path) -> list[str]:
    root = root.resolve()
    problems = find_problems(root)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    problems += packet_problems(manifest, packet.resolve(), root / ASSETS)
    problems += source_history_problems(root, manifest)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--packet-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        errors = verify(args.root, args.packet_dir)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f"E6 original capture verification input invalid: {type(exc).__name__}")
        return 1
    if errors:
        print("E6 original capture packet FAIL:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("E6 original capture packet PASS: every approved PNG matches original sidecar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
