"""Run the E1 Windows capture PoC with real, fresh process boundaries.

Each capture process creates one QApplication and one scene. This runner still
writes a report when a Qt native access violation terminates a child process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
SCENES = ("single_image", "raw_profile_dialog")
ATTEMPTS = 2
MAX_CHANGED_FRACTION = 0.01


def validate_capture(path: Path, metadata: Path, scene: str, source_sha: str) -> dict[str, object]:
    """Read a real PNG and verify it is not merely a blank surface."""
    result = json.loads(metadata.read_text(encoding="utf-8"))
    if result["status"] != "captured" or result["scenario"] != scene:
        raise ValueError("capture metadata reports failure or wrong scenario")
    if result["source_sha"] != source_sha:
        raise ValueError("capture source SHA mismatch")
    if hashlib.sha256(path.read_bytes()).hexdigest() != result["image_sha256"]:
        raise ValueError("capture PNG hash mismatch")
    with Image.open(path) as opened:
        opened.verify()
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        if width < 400 or height < 350:
            raise ValueError("captured screen is smaller than the minimum useful UI")
        if max(ImageStat.Stat(image).stddev) < 7.0:
            raise ValueError("captured UI has insufficient pixel variation")
        geometry = result["geometry"]
        if not isinstance(geometry, dict) or geometry["pixel_png"] != [width, height]:
            raise ValueError("captured PNG dimensions disagree with QWidget.grab metadata")
    return result


def changed_fraction(first: Path, second: Path) -> float:
    with Image.open(first) as a, Image.open(second) as b:
        if a.size != b.size:
            return 1.0
        difference = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        channels = difference.split()
        union = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
        count_zero = union.histogram()[0]
        return 1.0 - count_zero / (a.width * a.height)


def run(output: Path, source_sha: str) -> int:
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "schema_version": 1,
        "source_sha": source_sha,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "scenes": {},
        "max_changed_fraction": MAX_CHANGED_FRACTION,
        "status": "failed",
    }
    success = True
    for scene in SCENES:
        results: list[dict[str, object]] = []
        for attempt in range(1, ATTEMPTS + 1):
            png = output / f"{scene}-{attempt}.png"
            meta = output / f"{scene}-{attempt}.json"
            command = [
                sys.executable,
                str(ROOT / "scripts/capture_ui_scene.py"),
                "--scene",
                scene,
                "--output",
                str(png),
                "--metadata",
                str(meta),
                "--source-sha",
                source_sha,
            ]
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = "0"
            # Never substitute Qt offscreen for real desktop rendering.
            if env.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
                raise RuntimeError("QT_QPA_PLATFORM=offscreen cannot qualify the Windows GUI PoC")
            entry: dict[str, object] = {"attempt": attempt, "process_exit": None}
            try:
                process = subprocess.run(
                    command,
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                entry["process_exit"] = process.returncode
                if process.returncode != 0:
                    entry["error"] = "capture_process_failed"
                    # Paths and incidental environment details are not copied
                    # into a downloadable public artifact.
                    entry["stderr_tail"] = process.stderr[-1200:].replace(str(ROOT), "<repo>")
                    success = False
                else:
                    metadata = validate_capture(png, meta, scene, source_sha)
                    entry["image_sha256"] = metadata["image_sha256"]
                    entry["geometry"] = metadata["geometry"]
                    entry["screen"] = metadata["screen"]
            except subprocess.TimeoutExpired:
                entry["error"] = "capture_process_timeout"
                success = False
            except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
                entry["error"] = type(exc).__name__
                success = False
            if meta.is_file():
                try:
                    entry["capture_status"] = json.loads(meta.read_text(encoding="utf-8"))["status"]
                except (ValueError, OSError, KeyError):
                    entry["capture_status"] = "invalid_metadata"
            print(
                f"{scene} attempt {attempt}: "
                f"exit={entry['process_exit']}, error={entry.get('error')}"
            )
            results.append(entry)
        scene_report: dict[str, object] = {"attempts": results}
        if all("image_sha256" in item for item in results):
            fraction = changed_fraction(output / f"{scene}-1.png", output / f"{scene}-2.png")
            scene_report["changed_pixel_fraction"] = fraction
            scene_report["identical_pixels"] = fraction == 0.0
            if fraction > MAX_CHANGED_FRACTION:
                success = False
                scene_report["repeatability_error"] = "changed pixels exceed PoC tolerance"
        report["scenes"][scene] = scene_report  # type: ignore[index]

    report["status"] = "passed" if success else "failed"
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "summary.md").write_text(
        "# WP-Help-E1 hosted Windows GUI proof of concept\n\n"
        f"- Source SHA: `{source_sha}`\n"
        f"- Result: **{report['status']}**\n"
        "- Scenes: real Single View and RAW profile dialog; two fresh processes each.\n"
        "- Pixel repeatability tolerance: 1% changed pixels; exact fraction in report.json.\n"
        "- Generated PNGs are candidate artifacts, not reviewed User Guide images.\n",
        encoding="utf-8",
    )
    return 0 if success else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    if len(args.source_sha) != 40 or not all(ch in "0123456789abcdef" for ch in args.source_sha):
        parser.error("--source-sha requires an exact lowercase Git SHA")
    return run(args.output_dir, args.source_sha)


if __name__ == "__main__":
    raise SystemExit(main())
