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
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/user-guide/assets/screenshots/manifest.json"
_MANIFEST_ROWS = json.loads(MANIFEST.read_text(encoding="utf-8"))["screenshots"]
SCENES = tuple(row["scenario"] for row in _MANIFEST_ROWS if row["capture_mode"] == "isolated")
ATTEMPTS = 2
MAX_CHANGED_FRACTION = 0.01
EXPECTED_LOGICAL_SIZE = {
    row["scenario"]: [row["viewport"]["width"], row["viewport"]["height"]]
    for row in _MANIFEST_ROWS
    if row["capture_mode"] == "isolated"
}
ALLOW_WIDGET_RESIZE = {
    row["scenario"]: row.get("geometry_policy", "resizable") == "resizable"
    for row in _MANIFEST_ROWS
    if row["capture_mode"] == "isolated"
}
CALLBACK_ERROR_MARKER = "PIXELSCOPE_E1_QT_CALLBACK_EXCEPTION"


def sanitized_stderr(stderr: str) -> str:
    """Record bounded diagnostic evidence without local paths or usernames."""
    text = stderr[-2400:].replace(str(ROOT), "<repo>").replace(str(Path.home()), "<home>")
    return re.sub(
        r"[A-Za-z]:[/\\][^\s'\"<>]*|/(?:home|Users|mnt|tmp|var|opt)/[^\s'\"<>]*",
        "<path>",
        text,
    )[-1200:]


def stderr_has_callback_exception(stderr: str) -> bool:
    """Distinguish Python/Qt callback tracebacks from benign Qt warnings."""
    return any(
        marker in stderr
        for marker in (
            CALLBACK_ERROR_MARKER,
            "Traceback (most recent call last):",
            "Error calling Python override",
        )
    )


def assess_capture_process(
    process: subprocess.CompletedProcess[str],
    png: Path,
    metadata_path: Path,
    scene: str,
    source_sha: str,
    *,
    expected_logical_size: list[int] | None = None,
    allow_widget_resize: bool = False,
) -> dict[str, object]:
    """Validate a real child; E4 supplies pinned manifest geometry for new scenes."""
    if process.returncode != 0:
        raise ValueError("capture_process_failed")
    if stderr_has_callback_exception(process.stderr):
        raise ValueError("qt_callback_exception")
    metadata = validate_capture(
        png,
        metadata_path,
        scene,
        source_sha,
        expected_logical_size=expected_logical_size,
        allow_widget_resize=allow_widget_resize,
    )
    if metadata.get("callback_errors"):
        raise ValueError("qt_callback_exception")
    return metadata


def validate_capture(
    path: Path,
    metadata: Path,
    scene: str,
    source_sha: str,
    *,
    expected_logical_size: list[int] | None = None,
    allow_widget_resize: bool = False,
) -> dict[str, object]:
    """Validate a real PNG; E1 defaults stay strict, E4 uses manifest viewport."""

    result = json.loads(metadata.read_text(encoding="utf-8"))
    if result["status"] != "captured" or result["scenario"] != scene:
        raise ValueError("capture metadata reports failure or wrong scenario")
    if result.get("callback_errors"):
        raise ValueError("capture metadata contains a Qt callback exception")
    if result["source_sha"] != source_sha:
        raise ValueError("capture source SHA mismatch")
    if hashlib.sha256(path.read_bytes()).hexdigest() != result["image_sha256"]:
        raise ValueError("capture PNG hash mismatch")
    with Image.open(path) as opened:
        opened.verify()
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        if width < 250 or height < 180:
            raise ValueError("captured screen is smaller than the minimum useful UI")
        if max(ImageStat.Stat(image).stddev) < 7.0:
            raise ValueError("captured UI has insufficient pixel variation")
        geometry = result["geometry"]
        if not isinstance(geometry, dict) or geometry["pixel_png"] != [width, height]:
            raise ValueError("captured PNG dimensions disagree with QWidget.grab metadata")
        actual_size = geometry.get("logical_widget")
        if (
            not isinstance(actual_size, list)
            or len(actual_size) != 2
            or any(not isinstance(n, int) or n <= 0 for n in actual_size)
        ):
            raise ValueError("invalid captured QWidget geometry")
        if expected_logical_size is None and result.get("capture_profile") == "windows-e1-poc-v1":
            # E1's original two-scene PoC remains strict. E4 never uses this
            # table: it provides viewport/policy from each pinned manifest.
            expected_logical_size = EXPECTED_LOGICAL_SIZE.get(scene)
            if expected_logical_size is None:
                raise ValueError("E1 scene requires explicit expected geometry")
        if (
            not allow_widget_resize
            and expected_logical_size is not None
            and actual_size != expected_logical_size
        ):
            raise ValueError(
                "capture_contract_geometry: widget geometry differs from pinned capture profile"
            )
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
                try:
                    metadata = assess_capture_process(
                        process,
                        png,
                        meta,
                        scene,
                        source_sha,
                        expected_logical_size=EXPECTED_LOGICAL_SIZE[scene],
                        allow_widget_resize=ALLOW_WIDGET_RESIZE[scene],
                    )
                except (OSError, KeyError, ValueError) as exc:
                    entry["error"] = (
                        str(exc)
                        if isinstance(exc, ValueError)
                        and str(exc) in {"capture_process_failed", "qt_callback_exception"}
                        else type(exc).__name__
                    )
                    if process.stderr:
                        entry["stderr_tail"] = sanitized_stderr(process.stderr)
                    success = False
                else:
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
                    capture_meta = json.loads(meta.read_text(encoding="utf-8"))
                    entry["capture_status"] = capture_meta["status"]
                    if capture_meta.get("error_type"):
                        entry["capture_error_type"] = capture_meta["error_type"]
                    if capture_meta.get("error_detail"):
                        entry["capture_error_detail"] = str(capture_meta["error_detail"])[:300]
                    if capture_meta.get("callback_errors"):
                        entry["callback_errors"] = capture_meta["callback_errors"][:8]
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
