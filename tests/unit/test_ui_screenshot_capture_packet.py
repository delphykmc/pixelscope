"""E6 original candidate sidecar attestation fails closed on provenance drift."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

from scripts.verify_ui_screenshot_capture_packet import ASSETS, MANIFEST, ROOT, packet_problems


def _packet(tmp_path: Path) -> tuple[dict, Path, Path]:
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    # One real checked-in PNG, plus a synthetic sidecar with matching file identity.
    row = manifest["screenshots"][0]
    assets = tmp_path / "assets"
    packet = tmp_path / "packet"
    assets.mkdir()
    packet.mkdir()
    shutil.copyfile(ROOT / ASSETS / row["filename"], assets / row["filename"])
    image = packet / (row["scenario"] + "-1.png")
    shutil.copyfile(assets / row["filename"], image)
    approved = row["approved"]
    sidecar = {
        "status": "captured",
        "scenario": row["scenario"],
        "source_sha": approved["capture_source_sha"],
        "application_version": approved["application_version"],
        "capture_profile": approved["comparison_profile_id"],
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "fixture_sha256": "c" * 64,
        "geometry": {
            "pixel_png": list(_dimensions(image)),
            "logical_widget": [row["viewport"]["width"], row["viewport"]["height"]],
        },
        "callback_errors": [],
        "error_type": None,
    }
    (packet / (row["scenario"] + "-1.json")).write_text(json.dumps(sidecar), encoding="utf-8")
    manifest["screenshots"] = [copy.deepcopy(row)]
    return manifest, packet, assets


def _dimensions(image: Path) -> tuple[int, int]:
    import struct

    return struct.unpack_from(">II", image.read_bytes(), 16)


def test_original_sidecar_and_approved_bytes_can_be_bound(tmp_path: Path) -> None:
    manifest, packet, assets = _packet(tmp_path)
    assert packet_problems(manifest, packet, assets) == []


def test_wrong_source_and_profile_are_not_satisfied_by_matching_manifest_hash(
    tmp_path: Path,
) -> None:
    manifest, packet, assets = _packet(tmp_path)
    p = next(packet.glob("*.json"))
    sidecar = json.loads(p.read_text(encoding="utf-8"))
    sidecar["source_sha"] = "0" * 40
    sidecar["capture_profile"] = "other-host"
    p.write_text(json.dumps(sidecar), encoding="utf-8")
    errors = packet_problems(manifest, packet, assets)
    assert any("sidecar source_sha" in error for error in errors)
    assert any("sidecar capture_profile" in error for error in errors)


def test_wrong_original_bytes_do_not_pass_even_with_same_source_sha(tmp_path: Path) -> None:
    manifest, packet, assets = _packet(tmp_path)
    candidate = next(packet.glob("*.png"))
    candidate.write_bytes(b"not the reviewed screenshot")
    errors = packet_problems(manifest, packet, assets)
    assert any("original candidate, committed PNG" in error for error in errors)
    assert any("PNG" in error for error in errors)


def test_missing_original_sidecar_and_incorrect_geometry_fail(tmp_path: Path) -> None:
    manifest, packet, assets = _packet(tmp_path)
    p = next(packet.glob("*.json"))
    sidecar = json.loads(p.read_text(encoding="utf-8"))
    sidecar["geometry"]["pixel_png"] = [800, 600]
    p.write_text(json.dumps(sidecar), encoding="utf-8")
    assert any(
        "sidecar PNG dimensions" in error for error in packet_problems(manifest, packet, assets)
    )
    p.unlink()
    assert any(
        "candidate PNG and JSON sidecar" in error
        for error in packet_problems(manifest, packet, assets)
    )
