"""Deterministic synthetic screenshot fixture identity; no native Qt imports.

Hash actual pixel bytes *and* the public-safe labels/path shown in Files so
changing a fixture's visible identity cannot masquerade as a UI code change.
Never pass a user's private input paths to this screenshot-only helper.
"""

from __future__ import annotations

import hashlib
import json


def single_view_fixture_identity(
    pixels: bytes,
    display_name: str,
    synthetic_source_path: str,
) -> str:
    descriptor = {
        "schema_version": 1,
        "pixel_sha256": hashlib.sha256(pixels).hexdigest(),
        "display_name": display_name,
        "synthetic_source_path": synthetic_source_path,
    }
    return hashlib.sha256(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
