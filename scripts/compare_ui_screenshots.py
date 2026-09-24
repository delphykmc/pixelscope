"""Qt-free E4 image comparison and explicit, provenance-safe result semantics.

Never treat a target profile or an unverified checked-in image as a historical
capture fingerprint. Comparability uses actual base/head sidecars and immutable
scene builder ASTs; source/version/runner identifiers are provenance only.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

SCENE_FUNCTIONS = {"single_image": "_single_image", "raw_profile_dialog": "_raw_dialog"}
RUNTIME_KEYS = ("capture_profile", "python", "qt", "pyside6", "pyqtgraph")
SCREEN_KEYS = ("logical_dpi", "physical_dpi", "device_pixel_ratio")
GEOMETRY_KEYS = ("logical_widget", "device_pixel_ratio")


def scene_contract(root: Path, scenario: str) -> str:
    """A builder's semantic AST, not source commit/formatting/app version."""
    function = SCENE_FUNCTIONS.get(scenario)
    if function is None:
        raise ValueError("E4 cannot assert a contract for an unregistered scene")
    tree = ast.parse((root / "scripts/capture_ui_scene.py").read_text(encoding="utf-8"))
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function]
    if len(matches) != 1:
        raise ValueError("isolated scene builder missing or ambiguous at pinned revision")
    return hashlib.sha256(ast.dump(matches[0], include_attributes=False).encode()).hexdigest()


def fingerprint(meta: dict[str, Any], environment: dict[str, Any]) -> dict[str, Any]:
    """Exclude SHA, app version, machine name, timestamps, screenshots and paths."""
    geometry = meta.get("geometry")
    screen = meta.get("screen")
    if not isinstance(geometry, dict) or not isinstance(screen, dict):
        raise ValueError("capture is missing effective widget/screen geometry")
    if not isinstance(environment, dict) or not environment:
        raise ValueError("missing renderer environment probe")
    result = {key: meta.get(key) for key in RUNTIME_KEYS}
    result["screen"] = {key: screen.get(key) for key in SCREEN_KEYS}
    result["geometry"] = {key: geometry.get(key) for key in GEOMETRY_KEYS}
    result["renderer_probe"] = environment
    if any(value is None for value in result.values()) or any(
        value is None for value in result["screen"].values()
    ) or any(value is None for value in result["geometry"].values()):
        raise ValueError("incomplete capture comparability metadata")
    return result


def pixel_metrics(base: Path, head: Path, output: Path | None = None) -> dict[str, Any]:
    """Exact decoded RGB pixels decide CHANGED; no tolerance masks text."""
    with Image.open(base) as a, Image.open(head) as z:
        a.load()
        z.load()
        if a.format != "PNG" or z.format != "PNG":
            raise ValueError("expected real PNG captures")
        first, second = a.convert("RGB"), z.convert("RGB")
    if first.size != second.size:
        return {
            "identical": False,
            "dimension_changed": True,
            "base_size": list(first.size),
            "head_size": list(second.size),
            "changed_pixel_fraction": 1.0,
            "max_channel_error": None,
            "mean_channel_error": None,
        }
    diff = ImageChops.difference(first, second)
    extrema = diff.getextrema()
    assert isinstance(extrema, tuple)
    max_error = max(high for _, high in extrema)
    if max_error and output is not None:
        output.mkdir(parents=True, exist_ok=True)
        combined = Image.new("RGB", (first.width * 2, first.height))
        combined.paste(first, (0, 0))
        combined.paste(second, (first.width, 0))
        combined.save(output / "side-by-side.png")
        diff.save(output / "diff.png")
    bands = diff.split()
    any_channel = ImageChops.lighter(ImageChops.lighter(bands[0], bands[1]), bands[2])
    fraction = 1.0 - any_channel.histogram()[0] / (first.width * first.height)
    return {
        "identical": max_error == 0,
        "dimension_changed": False,
        "base_size": list(first.size),
        "head_size": list(second.size),
        "changed_pixel_fraction": fraction,
        "max_channel_error": max_error,
        "mean_channel_error": sum(ImageStat.Stat(diff).mean) / 3,
    }


def compare_pair(
    base_png: Path,
    head_png: Path,
    base_meta: dict[str, Any],
    head_meta: dict[str, Any],
    base_environment: dict[str, Any],
    head_environment: dict[str, Any],
    base_contract: str,
    head_contract: str,
    base_record: dict[str, Any],
    head_record: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    """Return a status; incompatible captures never produce misleading diffs."""
    for key in ("scenario", "viewport"):
        if base_record.get(key) != head_record.get(key):
            return {"status": "BASELINE_INCOMPATIBLE", "reason": f"changed {key}"}
    if base_contract != head_contract:
        return {"status": "BASELINE_INCOMPATIBLE", "reason": "changed scene builder contract"}
    if base_meta.get("fixture_sha256") != head_meta.get("fixture_sha256"):
        return {"status": "BASELINE_INCOMPATIBLE", "reason": "different actual fixture bytes"}
    if not base_meta.get("fixture_sha256"):
        return {"status": "BASELINE_INCOMPATIBLE", "reason": "missing fixture identity"}
    try:
        first = fingerprint(base_meta, base_environment)
        second = fingerprint(head_meta, head_environment)
    except (KeyError, TypeError, ValueError) as exc:
        return {"status": "ENVIRONMENT_MISMATCH", "reason": str(exc)}
    if first != second:
        keys = sorted(key for key in first if first[key] != second[key])
        return {"status": "ENVIRONMENT_MISMATCH", "different_fields": keys}
    try:
        metrics = pixel_metrics(base_png, head_png, output)
    except (OSError, ValueError) as exc:
        return {"status": "COMPARISON_FAILED", "reason": type(exc).__name__}
    return {"status": "UNCHANGED" if metrics["identical"] else "CHANGED", **metrics}


def documentation_relation(root: Path, record: dict[str, Any], head_png: Path) -> dict[str, Any]:
    """A pixel difference is review debt, NOT proof legacy PNGs are stale."""
    path = root / "docs/user-guide/assets/screenshots" / record["filename"]
    if not path.is_file():
        return {"state": "MISSING", "provenance": record.get("status")}
    try:
        metrics = pixel_metrics(path, head_png)
    except (OSError, ValueError):
        return {"state": "INVALID_COMMITTED_IMAGE", "provenance": record.get("status")}
    return {
        "state": "SAME_PIXELS" if metrics["identical"] else "DIFFERENT_PIXELS_REVIEW",
        "provenance": record.get("status"),
        "approved": bool(record.get("approved")),
        "note": "legacy-unverified image cannot establish historical capture SHA",
    }
