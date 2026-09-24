"""E6 read-only screenshot coverage and owner-decision audit.

Existing Guide PNGs, approved provenance and planned scenes are different facts.
This tool does not capture UI, copy images, rewrite a manifest or infer approval
from a URL. An E6 decision must first be explicitly recorded by the owner in a
reviewed source change. A pending entry is intentionally NOT E6 completion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__:
    from .check_screenshot_manifest import find_problems as manifest_problems
else:
    from check_screenshot_manifest import find_problems as manifest_problems

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("docs/user-guide/assets/screenshots/manifest.json")
DECISIONS = Path("docs/exec-plans/active/wp-help-e6-coverage-decisions.json")
ASSETS = MANIFEST.parent
BASE_FIELDS = {"id", "decision", "review_ref", "reason", "follow_up"}
EXISTING = {"pending", "promoted", "retained", "deferred"}
GAPS = {"pending", "promoted", "deferred"}


def _review_link(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlsplit(value)
    # The tool cannot verify who posted a review; this only excludes unknown
    # refs, placeholders, inline SHA guesses and local/private-file URLs.
    return parsed.scheme == "https" and bool(parsed.netloc and parsed.path.strip("/"))


def decision_problems(
    manifest: dict[str, Any], decisions: dict[str, Any], asset: Path
) -> list[str]:
    """Check per-ID owner decisions against *real* manifest/image evidence."""
    errors: list[str] = []
    if decisions.get("schema_version") != 1 or decisions.get("phase") != "WP-Help-E6":
        errors.append("E6 decision schema_version/phase is invalid")
    rows = manifest["screenshots"]
    by_id = {row["id"]: row for row in rows}
    # Stable *historical* cohorts: a gap stays a gap after gaining a real
    # isolated builder; migration must not silently reclassify its decision.
    expected = {
        "existing": {row["id"] for row in rows if row.get("legacy_output") is not None},
        "gaps": {row["id"] for row in rows if row.get("legacy_output") is None},
    }
    for group in ("existing", "gaps"):
        items = decisions.get(group)
        if not isinstance(items, list):
            errors.append(f"E6 {group} decisions must be a list")
            continue
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != BASE_FIELDS:
                errors.append(f"E6 {group} record has invalid fields")
                continue
            key = item["id"]
            if not isinstance(key, str) or key not in expected[group]:
                errors.append(f"E6 {group} record has unknown/misgrouped ID: {key}")
                continue
            if key in seen:
                errors.append(f"E6 duplicate decision: {key}")
            seen.add(key)
            state = item["decision"]
            if state not in (EXISTING if group == "existing" else GAPS):
                errors.append(f"E6 invalid decision for {key}: {state}")
                continue
            if state == "pending":
                if any(item[field] is not None for field in ("review_ref", "reason", "follow_up")):
                    errors.append(f"E6 pending {key} must not invent owner evidence")
                continue
            if not _review_link(item["review_ref"]):
                errors.append(f"E6 {key}: explicit external owner review reference required")
            if state == "promoted":
                row = by_id[key]
                source = asset / row["filename"]
                if row["status"] != "approved" or not source.is_file():
                    errors.append(f"E6 {key}: promoted requires approved manifest and present PNG")
                else:
                    approved = row.get("approved") or {}
                    if (
                        approved.get("approval_ref") != item["review_ref"]
                        or hashlib.sha256(source.read_bytes()).hexdigest()
                        != approved.get("image_sha256")
                    ):
                        errors.append(f"E6 {key}: approval ref or image bytes disagree")
                if group == "gaps" and (
                    row["capture_mode"] != "isolated" or row["placement"] != "required"
                ):
                    errors.append(f"E6 {key}: planned gap lacks verified real isolated scene")
                if item["reason"] is not None or item["follow_up"] is not None:
                    errors.append(f"E6 {key}: promoted needs no defer/retain reason")
            elif state in ("retained", "deferred"):
                if not isinstance(item["reason"], str) or len(item["reason"].strip()) < 20:
                    errors.append(f"E6 {key}: explicit technical/visual rationale required")
                if state == "deferred" and not _review_link(item["follow_up"]):
                    errors.append(f"E6 {key}: deferred requires concrete future follow-up URL")
                if state == "retained":
                    if by_id[key]["status"] != "legacy-unverified":
                        errors.append(f"E6 {key}: retained cannot assert new capture approval")
                    if item["follow_up"] is not None:
                        errors.append(f"E6 {key}: retained cannot claim deferred follow-up")
        for missing in sorted(expected[group] - seen):
            errors.append(f"E6 missing individual {group} decision: {missing}")
    if set(decisions) != {"schema_version", "phase", "existing", "gaps"}:
        errors.append("E6 decision file has unknown/missing top-level fields")
    return errors


def audit(root: Path = ROOT, *, require_complete: bool = False) -> dict[str, Any]:
    root = root.resolve()
    errors = manifest_problems(root)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    decisions = json.loads((root / DECISIONS).read_text(encoding="utf-8"))
    errors += decision_problems(manifest, decisions, root / ASSETS)
    pending = [
        row["id"]
        for group in ("existing", "gaps")
        for row in decisions.get(group, [])
        if isinstance(row, dict) and row.get("decision") == "pending"
    ]
    if require_complete and pending:
        errors.append(f"E6 not complete; {len(pending)} individual owner decisions pending")
    return {
        "schema_version": 1,
        "complete": not errors and not pending,
        "existing": len(decisions.get("existing", [])),
        "gaps": len(decisions.get("gaps", [])),
        "pending_ids": pending,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = audit(args.root, require_complete=args.require_complete)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"E6 audit input invalid: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
