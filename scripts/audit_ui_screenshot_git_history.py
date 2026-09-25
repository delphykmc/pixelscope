"""Derive screenshot introducing commits from actual refs, never from manifest guesses.

Run after E6 merge with --ref main, and again against the release tag.
Old tags are audited against their own manifest/image snapshot (rollback),
rather than falsely applying today's screenshot hashes to historical releases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "docs/user-guide/assets/screenshots/manifest.json"
ASSET = "docs/user-guide/assets/screenshots/"


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=False,
        timeout=20,
    )
    if result.returncode:
        raise ValueError("Git object/ref unavailable or invalid")
    return result.stdout


def audit_ref(root: Path, ref: str) -> dict[str, Any]:
    """Validate approved exact blobs and report their historical introducing SHA."""
    root = root.resolve()
    # Resolve refs, including annotated tags. Do not guess squash/rebase SHAs.
    commit = _git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    data = json.loads(_git(root, "show", f"{commit}:{MANIFEST}"))
    cases: list[dict[str, str]] = []
    errors: list[str] = []
    for row in data["screenshots"]:
        key = row["id"]
        if row["status"] != "approved":
            # A pre-E6 tag may legitimately retain legacy/unapproved old bytes.
            continue
        path = ASSET + row["filename"]
        approved = row["approved"]
        try:
            blob = _git(root, "show", f"{commit}:{path}")
            introducing = _git(
                root, "log", "-n", "1", "--format=%H", commit, "--", path
            ).decode().strip()
        except ValueError:
            errors.append(f"{key}: approved PNG/blob missing at {ref}")
            continue
        if hashlib.sha256(blob).hexdigest() != approved.get("image_sha256"):
            errors.append(f"{key}: approved PNG/blob hash drift at {ref}")
        if len(introducing) != 40:
            errors.append(f"{key}: cannot derive introducing Git commit at {ref}")
        else:
            cases.append({
                "id": key,
                "image_sha256": hashlib.sha256(blob).hexdigest(),
                "introducing_commit": introducing,
                "capture_source_sha": approved["capture_source_sha"],
            })
    return {"ref": ref, "resolved_commit": commit, "approved_images": cases, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument(
        "--release-ref", help="Optional actual release tag/ref to audit independently"
    )
    args = parser.parse_args(argv)
    try:
        reports = [audit_ref(args.root, args.ref)]
        if args.release_ref:
            reports.append(audit_ref(args.root, args.release_ref))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f"E6 Git history audit FAIL: {type(exc).__name__}")
        return 1
    print(json.dumps(reports, indent=2, sort_keys=True))
    return int(any(report["errors"] for report in reports))


if __name__ == "__main__":
    raise SystemExit(main())
