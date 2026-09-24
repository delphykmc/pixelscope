"""Qt-free E4 image comparison and explicit, provenance-safe result semantics.

Never treat a target profile or an unverified checked-in image as a historical
capture fingerprint. Comparability uses actual base/head sidecars and immutable
scene builder ASTs; source/version/runner identifiers are provenance only.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

RUNTIME_KEYS = ("capture_profile", "python", "qt", "pyside6", "pyqtgraph")
SCREEN_KEYS = ("logical_dpi", "physical_dpi", "device_pixel_ratio")
GEOMETRY_KEYS = ("device_pixel_ratio",)


def scene_contract(root: Path, scenario: str) -> str:
    """Resolve the actual pinned BUILDERS registry and hash its real scene AST.

    Never maintain a parallel two-scene mapping that fails once E5/E6 adds a
    reviewed isolated builder. Qt is not imported or executed to do this.
    """
    tree = ast.parse((root / "scripts/capture_ui_scene.py").read_text(encoding="utf-8"))
    registry = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "BUILDERS" for t in node.targets)
    ]
    if len(registry) != 1 or not isinstance(registry[0], ast.Dict):
        raise ValueError("missing or ambiguous pinned BUILDERS registry")
    mapping: dict[str, str] = {}
    for key, value in zip(registry[0].keys, registry[0].values, strict=True):
        if (
            not isinstance(key, ast.Constant)
            or not isinstance(key.value, str)
            or not isinstance(value, ast.Name)
            or key.value in mapping
        ):
            raise ValueError("invalid pinned BUILDERS registry entry")
        mapping[key.value] = value.id
    function = mapping.get(scenario)
    if function is None:
        raise ValueError("E4 cannot assert a contract for an unregistered scene")
    matches = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function
    ]
    if len(matches) != 1:
        raise ValueError("isolated scene builder missing or ambiguous at pinned revision")
    return hashlib.sha256(ast.dump(matches[0], include_attributes=False).encode()).hexdigest()


def fingerprint(meta: dict[str, Any], environment: dict[str, Any]) -> dict[str, Any]:
    """Exclude provenance AND actual QWidget extent from renderer comparability."""
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
    if (
        any(value is None for value in result.values())
        or any(value is None for value in result["screen"].values())
        or any(value is None for value in result["geometry"].values())
    ):
        raise ValueError("incomplete capture comparability metadata")
    return result


def pixel_metrics(base: Path, head: Path, output: Path | None = None) -> dict[str, Any]:
    """Exact decoded RGB pixels decide CHANGED; no tolerance masks text."""
    with Image.open(base) as a, Image.open(head) as z:
        a.load()
        z.load()
        if a.format != "PNG" or z.format != "PNG":
            raise ValueError("expected real PNG captures")
        # E2 accepts both RGB and RGBA. Normalize to RGBA if either PNG has
        # alpha: an alpha-only change is a real decoded-pixel difference.
        use_alpha = a.mode == "RGBA" or z.mode == "RGBA"
        mode = "RGBA" if use_alpha else "RGB"
        first, second = a.convert(mode), z.convert(mode)
    if first.size != second.size:
        # Incompatible extents are a CHANGED UI result, not an excuse to omit
        # the promised review artifact. Pad *only the diagnostics*: never use
        # synthetic padding to declare two captured regions identical.
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
            canvas_width = max(first.width, second.width)
            canvas_height = max(first.height, second.height)
            base_canvas = Image.new(mode, (canvas_width, canvas_height))
            head_canvas = Image.new(mode, (canvas_width, canvas_height))
            base_canvas.paste(first, (0, 0))
            head_canvas.paste(second, (0, 0))
            combined = Image.new(mode, (canvas_width * 2, canvas_height))
            combined.paste(base_canvas, (0, 0))
            combined.paste(head_canvas, (canvas_width, 0))
            combined.save(output / "side-by-side.png")
            diagnostic = ImageChops.difference(base_canvas, head_canvas)
            if use_alpha:
                # Expose alpha-only differences in a visible grayscale delta.
                channels = diagnostic.split()
                union = channels[0]
                for band in channels[1:]:
                    union = ImageChops.lighter(union, band)
                diagnostic = Image.merge("RGB", (union, union, union))
            diagnostic.save(output / "diff.png")
        return {
            "identical": False,
            "dimension_changed": True,
            "base_size": list(first.size),
            "head_size": list(second.size),
            "changed_pixel_fraction": 1.0,
            "max_channel_error": None,
            "mean_channel_error": None,
            "diagnostic_note": "padded visual artifact; dimensions differ",
        }
    diff = ImageChops.difference(first, second)
    extrema = diff.getextrema()
    assert isinstance(extrema, tuple)
    max_error = max(high for _, high in extrema)
    bands = diff.split()
    if max_error and output is not None:
        output.mkdir(parents=True, exist_ok=True)
        combined = Image.new("RGB", (first.width * 2, first.height))
        combined.paste(first, (0, 0))
        combined.paste(second, (first.width, 0))
        combined.save(output / "side-by-side.png")
        if use_alpha:
            diagnostic = bands[0]
            for band in bands[1:]:
                diagnostic = ImageChops.lighter(diagnostic, band)
            Image.merge("RGB", (diagnostic, diagnostic, diagnostic)).save(output / "diff.png")
        else:
            diff.save(output / "diff.png")
    any_channel = bands[0]
    for band in bands[1:]:
        any_channel = ImageChops.lighter(any_channel, band)
    fraction = 1.0 - any_channel.histogram()[0] / (first.width * first.height)
    return {
        "identical": max_error == 0,
        "dimension_changed": False,
        "base_size": list(first.size),
        "head_size": list(second.size),
        "changed_pixel_fraction": fraction,
        "max_channel_error": max_error,
        "mean_channel_error": sum(ImageStat.Stat(diff).mean) / len(bands),
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
    # A capture's metadata must describe its real PNG, not conceal geometry
    # corruption as a legitimate UI resize. E4 validates this after each
    # child process as well, but keep the comparator independently fail-closed.
    try:
        with Image.open(base_png) as left, Image.open(head_png) as right:
            for image, meta in ((left, base_meta), (right, head_meta)):
                geometry = meta.get("geometry", {})
                if not isinstance(geometry, dict) or geometry.get("pixel_png") != list(image.size):
                    return {
                        "status": "COMPARISON_FAILED",
                        "reason": "PNG dimensions disagree with capture metadata",
                    }
    except (OSError, ValueError, TypeError):
        return {"status": "COMPARISON_FAILED", "reason": "invalid capture PNG"}
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
