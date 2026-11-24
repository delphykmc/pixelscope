"""Capture, review and explicitly promote the complete current guide on Windows."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from audit_ui_screenshot_coverage import DECISIONS, audit
from check_screenshot_manifest import find_problems
from run_ui_capture_poc import (
    MAX_CHANGED_FRACTION,
    assess_capture_process,
    changed_fraction,
    validate_capture,
)
from verify_ui_screenshot_capture_packet import ASSETS, MANIFEST, packet_problems

ROOT = Path(__file__).resolve().parents[1]
VERSION = runpy.run_path(str(ROOT / "src/pixelscope/version.py"))["__version__"]


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def require_clean() -> str:
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("Tracked worktree is dirty; commit or stash before capture/promotion")
    problems = find_problems(ROOT)
    if problems:
        raise RuntimeError("\n".join(problems))
    return git("rev-parse", "HEAD")


def validate_row(row: dict, png: Path, meta: Path, source: str, profile: str) -> dict:
    size = row["viewport"]
    result = validate_capture(
        png,
        meta,
        row["scenario"],
        source,
        expected_logical_size=[size["width"], size["height"]],
        allow_widget_resize=row.get("geometry_policy") == "resizable",
    )
    if (
        result.get("application_version") != VERSION
        or result.get("capture_profile") != profile
        or result.get("error_type")
        or not re.fullmatch("[0-9a-f]{64}", str(result.get("fixture_sha256")))
    ):
        raise ValueError("capture version/profile/fixture identity mismatch")
    return result


def candidate_rows(packet: Path, manifest: dict, source: str) -> list[dict]:
    results = []
    profile = manifest["target_capture_profile"]
    for row in manifest["screenshots"]:
        key = row["id"]
        first = packet / f"{key}.png"
        second = packet / "repeat" / f"{key}.png"
        a = validate_row(row, first, first.with_suffix(".json"), source, profile)
        b = validate_row(row, second, second.with_suffix(".json"), source, profile)
        if a["fixture_sha256"] != b["fixture_sha256"]:
            raise ValueError(f"{key}: fixture changed between captures")
        if changed_fraction(first, second) > MAX_CHANGED_FRACTION:
            raise ValueError(f"{key}: repeatability exceeded existing tolerance")
        results.append(a)
    return results


def review(packet: Path, manifest: dict, source: str, results: list[dict]) -> None:
    lines = [
        f"Guide screenshot approval candidate: Core {VERSION}",
        f"Capture source SHA: `{source}`",
        "",
        "| Screenshot ID | PNG SHA-256 |",
        "|---|---|",
    ]
    cards = []
    for row, result in zip(manifest["screenshots"], results, strict=True):
        key = row["id"]
        digest = result["image_sha256"]
        lines.append(f"| {key} | `{digest}` |")
        old = ROOT / ASSETS / row["filename"]
        old_html = "<p>No previous guide PNG.</p>"
        if old.is_file():
            previous = packet / "previous" / row["filename"]
            previous.parent.mkdir(exist_ok=True)
            shutil.copyfile(old, previous)
            old_html = f'<a href="previous/{key}.png"><img src="previous/{key}.png"></a>'
        cards.append(
            f"<section><h2>{html.escape(key)}</h2>"
            f"<p>{html.escape(', '.join(row['pages']))}</p><code>{digest}</code>"
            '<div class="pair"><div><h3>Previous</h3>'
            f"{old_html}</div><div><h3>Candidate</h3>"
            f'<a href="{key}.png"><img src="{key}.png"></a></div></div></section>'
        )
    lines += ["", "I visually reviewed and approve the exact candidate PNG hashes above."]
    (packet / "approval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = '<p><a href="memo-report/index.html">Actual generated Memo HTML report</a></p>'
    (packet / "review.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Guide screenshot review</title>'
        "<style>body{font:15px system-ui;margin:24px;background:#eee;color:#222}"
        "section{background:white;padding:16px;margin:16px 0}.pair{display:grid;"
        "grid-template-columns:1fr 1fr;gap:12px}img{max-width:100%;height:auto}"
        "code{overflow-wrap:anywhere}</style>"
        f"<h1>Core {VERSION} screenshot review</h1><p>{source}</p>"
        "<p>Click images to view original pixels. Review labels, crop and privacy.</p>"
        + report
        + "".join(cards),
        encoding="utf-8",
    )


def capture(packet: Path, manifest: dict, source: str) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Native Windows capture is required")
    if packet.is_relative_to(ROOT / ASSETS):
        raise ValueError("Candidate packet must not be inside guide assets")
    packet.mkdir(parents=True, exist_ok=True)
    repeat = packet / "repeat"
    repeat.mkdir(exist_ok=True)
    env = dict(os.environ, QT_SCALE_FACTOR="1", PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
    env.pop("QT_QPA_PLATFORM", None)
    profile = manifest["target_capture_profile"]
    failures = []
    for row in manifest["screenshots"]:
        key = row["id"]
        print(f"Capture {key}", flush=True)
        try:
            for folder in (packet, repeat):
                png = folder / f"{key}.png"
                meta = png.with_suffix(".json")
                try:
                    validate_row(row, png, meta, source, profile)
                    if folder != packet or key != "memo-workspace" or (
                        packet / "memo-report/index.html"
                    ).is_file():
                        continue
                except (OSError, ValueError, KeyError, TypeError):
                    pass
                png.unlink(missing_ok=True)
                meta.unlink(missing_ok=True)
                cmd = [
                    sys.executable,
                    str(ROOT / "scripts/capture_ui_scene.py"),
                    "--scene",
                    row["scenario"],
                    "--output",
                    str(png),
                    "--metadata",
                    str(meta),
                    "--source-sha",
                    source,
                ]
                if key == "memo-workspace" and folder == packet:
                    if (packet / "memo-report").exists():
                        raise RuntimeError("Remove only the stale memo-report folder and retry")
                    cmd += ["--memo-report", str(packet / "memo-report/inspection.pxmemo")]
                process = subprocess.run(
                    cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120
                )
                png.with_suffix(".log").write_text(
                    process.stdout + "\n" + process.stderr, encoding="utf-8"
                )
                size = row["viewport"]
                assess_capture_process(
                    process,
                    png,
                    meta,
                    row["scenario"],
                    source,
                    expected_logical_size=[size["width"], size["height"]],
                    allow_widget_resize=row.get("geometry_policy") == "resizable",
                )
                validate_row(row, png, meta, source, profile)
            if changed_fraction(packet / f"{key}.png", repeat / f"{key}.png") > (
                MAX_CHANGED_FRACTION
            ):
                (repeat / f"{key}.png").unlink()
                raise ValueError("repeatability failed; rerun to retry second capture")
        except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
            failures.append(f"{key}: {exc}")
    if failures:
        raise RuntimeError("Capture failures (rerun same command to resume):\n" + "\n".join(failures))
    results = candidate_rows(packet, manifest, source)
    review(packet, manifest, source, results)
    print(f"Review: {packet / 'review.html'}")
    print(f"Approval hashes: {packet / 'approval.md'}")


def promote(packet: Path, manifest: dict, source: str, approval: str) -> None:
    if not re.fullmatch(
        r"https://github\.com/[^/]+/[^/]+/pull/\d+#issuecomment-\d+", approval
    ):
        raise ValueError("Supply the actual owner approval PR comment URL")
    results = candidate_rows(packet, manifest, source)
    # Require the reviewed hash list to match these exact bytes before copying.
    approved_text = (packet / "approval.md").read_text(encoding="utf-8")
    if f"`{source}`" not in approved_text:
        raise ValueError("approval list has the wrong capture source")
    decisions = read_json(ROOT / DECISIONS)
    by_id = {row["id"]: row for group in ("existing", "gaps") for row in decisions[group]}
    for row, result in zip(manifest["screenshots"], results, strict=True):
        key = row["id"]
        digest = result["image_sha256"]
        if f"| {key} | `{digest}` |" not in approved_text:
            raise ValueError(f"{key}: reviewed hash list differs")
        row["status"] = "approved"
        row["approved"] = {
            "capture_source_sha": source,
            "application_version": VERSION,
            "comparison_profile_id": result["capture_profile"],
            "scenario_contract_id": row["scenario"] + "-v1",
            "image_sha256": digest,
            "approval_ref": approval,
        }
        by_id[key].update(decision="promoted", review_ref=approval, reason=None, follow_up=None)
    # Validate in a temporary staging directory before touching tracked files.
    with tempfile.TemporaryDirectory(prefix="pixelscope-guide-promotion-") as tmp:
        staging = Path(tmp)
        for row in manifest["screenshots"]:
            shutil.copyfile(packet / row["filename"], staging / row["filename"])
        errors = packet_problems(manifest, packet, staging)
        if errors:
            raise RuntimeError("\n".join(errors))
        targets = [ROOT / ASSETS / row["filename"] for row in manifest["screenshots"]]
        targets += [ROOT / MANIFEST, ROOT / DECISIONS]
        originals = {path: path.read_bytes() if path.exists() else None for path in targets}
        try:
            for row in manifest["screenshots"]:
                shutil.copyfile(staging / row["filename"], ROOT / ASSETS / row["filename"])
            write_json(ROOT / MANIFEST, manifest)
            write_json(ROOT / DECISIONS, decisions)
            errors = audit(ROOT, require_complete=True)["errors"]
            if errors:
                raise RuntimeError("\n".join(errors))
        except BaseException:
            for path, payload in originals.items():
                if payload is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(payload)
            raise
    print("Promoted all reviewed PNGs locally. Inspect git diff and commit explicitly.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "promote"))
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--approval-ref")
    args = parser.parse_args()
    try:
        source = require_clean()
        manifest = read_json(ROOT / MANIFEST)
        packet = args.packet_dir.resolve()
        if packet.is_relative_to(ROOT / ASSETS):
            raise ValueError("Candidate packet must be separate from approved assets")
        if args.action == "capture":
            capture(packet, manifest, source)
        else:
            if not args.approval_ref:
                raise ValueError("Promotion requires an actual explicit owner approval reference")
            promote(packet, manifest, source, args.approval_ref)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Guide screenshot refresh failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
