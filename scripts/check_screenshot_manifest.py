"""Qt-free E2–E5 screenshot manifest, optional-PNG and marker contract checker.

Check the complete guide source/page graph without Qt, Pillow or network access.
A declared but absent PNG is intentionally valid; a present damaged PNG is not.
"""

from __future__ import annotations

import argparse
import ast
import json
import posixpath
import re
import struct
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ASSET = Path("docs/user-guide/assets/screenshots")
GUIDE = Path("docs/user-guide")
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SCENE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
MARKER = re.compile(r"<!--\s*pixelscope:screenshot\b[^\n]*?(?:-->|$)", re.MULTILINE)
STRICT_MARKER = re.compile(r"<!-- pixelscope:screenshot ([a-z][a-z0-9-]*) -->")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 64 * 1024 * 1024
MAX_DECODED_BYTES = 128 * 1024 * 1024
CAPTURE_MODES = {"isolated", "legacy-manual", "planned"}
PLACEMENTS = {"legacy-unreferenced", "planned", "required"}
STATUSES = {"legacy-unverified", "planned", "capture-ready", "approved"}


def png_problems(path: Path) -> list[str]:
    """Check PNG chunk CRC and bounded zlib/scanline decode without Pillow/Qt."""
    try:
        if path.stat().st_size > MAX_PNG_BYTES:
            return ["PNG exceeds 64 MiB validation limit"]
        data = path.read_bytes()
        if not data.startswith(PNG_HEADER):
            return ["invalid PNG signature"]
        offset = len(PNG_HEADER)
        chunks: list[tuple[bytes, bytes]] = []
        while offset + 12 <= len(data):
            length = struct.unpack_from(">I", data, offset)[0]
            if length > MAX_PNG_BYTES or offset + 12 + length > len(data):
                return ["truncated/oversize PNG chunk"]
            kind = data[offset + 4 : offset + 8]
            payload = data[offset + 8 : offset + 8 + length]
            crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
            if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
                return ["PNG chunk CRC mismatch"]
            chunks.append((kind, payload))
            offset += 12 + length
            if kind == b"IEND":
                break
        if offset != len(data) or len(chunks) < 3:
            return ["PNG missing IEND or has trailing bytes"]
        if chunks[0][0] != b"IHDR" or len(chunks[0][1]) != 13:
            return ["missing/invalid PNG IHDR"]
        if chunks[-1] != (b"IEND", b""):
            return ["invalid PNG terminal chunk"]
        width, height, depth, color, compression, filt, interlace = struct.unpack(
            ">IIBBBBB", chunks[0][1]
        )
        if not 0 < width <= 20000 or not 0 < height <= 20000:
            return ["invalid PNG dimensions"]
        # E2 deliberately supports only the verified real QWidget PNG subset:
        # non-interlaced 8-bit RGB/RGBA. Other legal PNG encodings need a
        # dedicated decoder/Adam7/palette validation before being accepted.
        channels = {2: 3, 6: 4}.get(color)
        if channels is None or depth != 8 or compression != 0 or filt != 0 or interlace != 0:
            return ["unsupported PNG encoding: expected non-interlaced 8-bit RGB/RGBA"]
        payloads = [part for kind, part in chunks if kind == b"IDAT"]
        if not payloads:
            return ["PNG missing IDAT"]
        inflater = zlib.decompressobj()
        limit = MAX_DECODED_BYTES
        raw = inflater.decompress(b"".join(payloads), limit + 1)
        if len(raw) > limit or not inflater.eof or inflater.unused_data:
            return ["PNG IDAT exceeds limit or has invalid zlib stream"]
        pitch = (width * depth * channels + 7) // 8
        if (pitch + 1) * height != len(raw):
            return ["PNG decoded scanline length mismatch"]
        if any(raw[row * (pitch + 1)] > 4 for row in range(height)):
            return ["PNG has invalid scanline filter"]
        return []
    except (OSError, ValueError, struct.error, zlib.error, OverflowError) as exc:
        return [f"PNG decode/IO failure: {type(exc).__name__}"]


def _dict_keys_from_ast(path: Path, variable: str) -> set[str]:
    """Inspect literal Qt scene dispatch keys without importing native UI."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches: list[ast.Dict] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable for target in node.targets
        ):
            if not isinstance(node.value, ast.Dict):
                raise ValueError(f"{variable} must be a literal dict for static validation")
            matches.append(node.value)
    if len(matches) != 1:
        raise ValueError(f"expected one {variable} mapping")
    names = [key.value for key in matches[0].keys if isinstance(key, ast.Constant)]
    if len(names) != len(matches[0].keys) or not all(isinstance(key, str) for key in names):
        raise ValueError(f"{variable} must have literal string keys")
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate {variable} scene keys")
    return set(names)


def _legacy_outputs(path: Path) -> set[str]:
    """Existing manual grab destinations (not an independently maintained scenario list)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.endswith(".png")
        and node.value != ".png"
        and "/" not in node.value
        and "\\" not in node.value
    }


def find_problems(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    asset = root / ASSET
    guide = root / GUIDE
    problems: list[str] = []
    try:
        manifest = json.loads((asset / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"manifest cannot be read: {type(exc).__name__}"]
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["screenshot manifest schema_version must be 1"]
    if (
        not isinstance(manifest.get("target_capture_profile"), str)
        or not manifest["target_capture_profile"]
    ):
        problems.append("target_capture_profile is required")
    if manifest.get("impact_ownership_status") not in ("e3-pending", "complete"):
        problems.append("impact_ownership_status must be e3-pending or complete")
    shared = manifest.get("shared_source_globs", [])
    if (
        not isinstance(shared, list)
        or any(not isinstance(glob, str) or not glob for glob in shared)
        or len(shared) != len(set(map(str, shared)))
        or (manifest.get("impact_ownership_status") == "complete" and not shared)
    ):
        problems.append("E3 shared_source_globs must be a nonempty unique string list")
    screenshots = manifest.get("screenshots")
    if not isinstance(screenshots, list):
        return problems + ["screenshots must be a list"]

    try:
        isolated = _dict_keys_from_ast(root / "scripts/capture_ui_scene.py", "BUILDERS")
        manual = _legacy_outputs(root / "scripts/capture_ui_review.py")
    except (OSError, ValueError, SyntaxError) as exc:
        return problems + [f"scene registry cannot be checked: {type(exc).__name__}: {exc}"]

    by_id: dict[str, dict[str, Any]] = {}
    by_filename: set[str] = set()
    used_scenes: set[str] = set()
    manual_registered: set[str] = set()
    for index, record in enumerate(screenshots):
        prefix = f"screenshots[{index}]"
        if not isinstance(record, dict):
            problems.append(f"{prefix}: expected object")
            continue
        key = record.get("id")
        if not isinstance(key, str) or ID_RE.fullmatch(key) is None:
            problems.append(f"{prefix}: invalid screenshot ID")
            continue
        prefix = key
        if key in by_id:
            problems.append(f"{key}: duplicate screenshot ID")
            continue
        by_id[key] = record
        name = record.get("filename")
        if name != f"{key}.png" or not isinstance(name, str):
            problems.append(f"{key}: filename must be the canonical ID.png")
            continue
        if name in by_filename or name.lower() in {x.lower() for x in by_filename}:
            problems.append(f"{key}: duplicate/case-colliding PNG filename")
        by_filename.add(name)
        mode, placement, status = (
            record.get("capture_mode"),
            record.get("placement"),
            record.get("status"),
        )
        if mode not in CAPTURE_MODES or placement not in PLACEMENTS or status not in STATUSES:
            problems.append(f"{key}: invalid capture mode, placement or provenance status")
            continue
        pages = record.get("pages")
        if not isinstance(pages, list) or len(pages) != len(set(map(str, pages))):
            problems.append(f"{key}: pages must be a unique list")
            continue
        for page in pages:
            if (
                not isinstance(page, str)
                or page.startswith("/")
                or "\\" in page
                or ".." in Path(page).parts
                or not page.endswith(".md")
                or not (guide / page).is_file()
                or (guide / page).resolve().is_relative_to(guide.resolve()) is False
            ):
                problems.append(f"{key}: invalid or missing declared page: {page}")
        if placement in ("legacy-unreferenced",) and pages:
            problems.append(f"{key}: unreferenced placement must have no pages")
        if placement == "required" and not pages:
            problems.append(f"{key}: referenced placement requires pages")
        if placement == "planned" and (mode != "planned" or status != "planned"):
            problems.append(f"{key}: planned placement needs planned capture/status")
        if mode == "planned" and placement != "planned":
            problems.append(f"{key}: planned capture must use planned placement")
        if mode != "planned" and status == "planned":
            problems.append(f"{key}: existing scene may not report planned provenance")
        if status == "capture-ready" and mode != "isolated":
            problems.append(f"{key}: capture-ready requires a registered isolated scene")
        if (
            mode != "planned"
            and status == "legacy-unverified"
            and record.get("approved") is not None
        ):
            problems.append(f"{key}: legacy image must not invent approved provenance")
        if status == "approved":
            approved = record.get("approved")
            expected = {
                "capture_source_sha",
                "application_version",
                "comparison_profile_id",
                "scenario_contract_id",
                "image_sha256",
                "approval_ref",
            }
            if not isinstance(approved, dict) or set(approved) != expected:
                problems.append(f"{key}: invalid approved provenance fields")
            elif (
                not re.fullmatch("[0-9a-f]{40}", str(approved["capture_source_sha"]))
                or not re.fullmatch("[0-9a-f]{64}", str(approved["image_sha256"]))
                or not all(approved[field] for field in expected)
            ):
                problems.append(f"{key}: invalid approved provenance content")
        elif record.get("approved") is not None:
            problems.append(f"{key}: only approved status may carry approved metadata")
        if placement in ("planned", "legacy-unreferenced") and status == "approved":
            problems.append(f"{key}: approved PNG cannot be unreferenced/planned")
        scene = record.get("scenario")
        if not isinstance(scene, str) or not SCENE_RE.fullmatch(scene):
            problems.append(f"{key}: invalid scenario key")
        elif mode != "planned":
            if scene in used_scenes:
                problems.append(f"{key}: duplicate scene key; explicitly model shared scenes")
            used_scenes.add(scene)
            if mode == "isolated" and scene not in isolated:
                problems.append(f"{key}: no isolated real-UI builder registered for {scene}")
        legacy = record.get("legacy_output")
        # A new E2+ isolated builder has no historical manual output by design.
        # Legacy assets still require their real, uniquely owned capture output.
        if mode == "planned":
            if legacy is not None:
                problems.append(f"{key}: planned scene must not claim legacy capture")
        elif legacy is None:
            if mode != "isolated" or status not in ("capture-ready", "approved"):
                problems.append(f"{key}: legacy scene missing historical manual output")
        elif not isinstance(legacy, str) or legacy not in manual or legacy != f"{scene}.png":
            problems.append(f"{key}: no matching output in historical manual capture script")
        elif legacy in manual_registered:
            problems.append(f"{key}: duplicated historical manual output {legacy}")
        else:
            manual_registered.add(legacy)
        if not isinstance(record.get("alt"), str) or not record["alt"].strip():
            problems.append(f"{key}: alt text is required")
        if not isinstance(record.get("features"), list) or not record["features"]:
            problems.append(f"{key}: feature tags are required")
        globs = record.get("source_globs")
        if not isinstance(globs, list) or not all(isinstance(g, str) and g for g in globs):
            problems.append(f"{key}: source_globs must be a nonempty-string list")
        elif manifest.get("impact_ownership_status") == "complete" and not globs:
            problems.append(f"{key}: E3-complete impact ownership requires globs")
        elif len(globs) != len(set(globs)):
            problems.append(f"{key}: source_globs must be unique")
        viewport = record.get("viewport")
        if not isinstance(viewport, dict) or any(
            not isinstance(viewport.get(dim), int)
            or isinstance(viewport.get(dim), bool)
            or not 200 <= viewport[dim] <= 20000
            for dim in ("width", "height")
        ):
            problems.append(f"{key}: invalid capture viewport")
        policy = record.get("geometry_policy", "resizable")
        if policy not in ("fixed", "resizable"):
            problems.append(f"{key}: invalid capture geometry policy")
        actual = asset / name
        if actual.is_symlink():
            problems.append(f"{key}: screenshot symlinks are not permitted")
        elif actual.is_file():
            if placement == "planned":
                problems.append(f"{key}: planned scene has an unexpected committed PNG")
            if status == "capture-ready":
                problems.append(f"{key}: unapproved capture-ready PNG cannot be committed")
            problems.extend(f"{key}: {error}" for error in png_problems(actual))
            if status == "approved" and isinstance(record.get("approved"), dict):
                import hashlib

                if hashlib.sha256(actual.read_bytes()).hexdigest() != record["approved"].get(
                    "image_sha256"
                ):
                    problems.append(f"{key}: approved PNG hash mismatch")
        # A missing declared PNG is valid for every placement, including
        # previously existing legacy images and historically approved bytes.
        # A present declared PNG must still pass decode and approved SHA checks.

    diagnostics = manifest.get("diagnostic_legacy_outputs")
    if (
        not isinstance(diagnostics, list)
        or len(diagnostics) != len(set(map(str, diagnostics)))
        or any(not isinstance(name, str) or name not in manual for name in diagnostics)
    ):
        problems.append("diagnostic_legacy_outputs must reference unique manual PNG outputs")
    else:
        overlapping = manual_registered & set(diagnostics)
        if overlapping:
            problems.append(
                "manual output declared as both guide screenshot and diagnostic: "
                + ", ".join(sorted(overlapping))
            )
        if manual - manual_registered - set(diagnostics):
            problems.append(
                "manual capture outputs not classified in manifest: "
                + ", ".join(sorted(manual - manual_registered - set(diagnostics)))
            )
    if isolated - used_scenes:
        problems.append(
            "isolated real-UI builders missing from manifest: "
            + ", ".join(sorted(isolated - used_scenes))
        )

    declared = set(by_filename)
    for png in asset.glob("*.png"):
        if png.name not in declared:
            problems.append(f"unexpected screenshot PNG not in manifest: {png.name}")
    # E5: scan *all* source Markdown, including unnavlisted guide/asset pages.
    # A rendered image only comes from a declared required marker, never a
    # hard-coded PNG embed (which would become a broken link when omitted).
    for page in guide.rglob("*.md"):
        rel = page.relative_to(guide).as_posix()
        text = page.read_text(encoding="utf-8")
        observed: set[str] = set()
        for match in MARKER.finditer(text):
            strict = STRICT_MARKER.fullmatch(match.group())
            if strict is None:
                problems.append(f"{rel}: malformed screenshot marker")
                continue
            key = strict.group(1)
            if key not in by_id:
                problems.append(f"{rel}: unknown screenshot ID {key}")
                continue
            if by_id[key].get("placement") != "required" or rel not in by_id[key].get("pages", []):
                problems.append(f"{rel}: screenshot marker not declared for page: {key}")
            if key in observed:
                problems.append(f"{rel}: duplicate screenshot marker: {key}")
            observed.add(key)
        for match in IMAGE.finditer(text):
            target = match.group(1).split("#", 1)[0].split("?", 1)[0]
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
            if not resolved.startswith("assets/screenshots/"):
                continue
            name = resolved.removeprefix("assets/screenshots/")
            key = name.removesuffix(".png")
            if key not in by_id or by_id[key].get("filename") != name:
                problems.append(f"{rel}: undeclared literal screenshot image: {name}")
                continue
            problems.append(f"{rel}: hard-coded screenshot image forbidden: {key}")
            if key in observed:
                problems.append(f"{rel}: duplicate screenshot insertion: {key}")
            observed.add(key)
        for key, rec in by_id.items():
            if (
                rel in rec.get("pages", [])
                and rec.get("placement") == "required"
                and key not in observed
            ):
                problems.append(f"{rel}: missing required screenshot marker: {key}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    problems = find_problems(args.root)
    if problems:
        print("Screenshot manifest contract failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Screenshot manifest passed: conditional IDs, owned pages and present PNG assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
