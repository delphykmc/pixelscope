from __future__ import annotations

import json
from pathlib import Path

import pytest

import pixelscope.remote.iqa_submission as submission
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_storage import LogicalStoragePath, ResolvedSource
from pixelscope.remote.iqa_submission import FolderPairEntry, ImageProbe
from pixelscope.ui.iqa_request_debug import format_request_json, request_debug_enabled


def test_request_debug_requires_explicit_environment_opt_in() -> None:
    assert not request_debug_enabled({})
    assert request_debug_enabled({"PIXELSCOPE_REMOTE_IQA_DEBUG": "1"})
    assert request_debug_enabled({"PIXELSCOPE_REMOTE_IQA_DEBUG": "TRUE"})
    assert not request_debug_enabled({"PIXELSCOPE_REMOTE_IQA_DEBUG": "0"})


def test_request_debug_serializes_the_production_builder_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_a = tmp_path / "a.png"
    source_b = tmp_path / "b.png"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")
    entries = (
        FolderPairEntry(
            "scene_000000",
            ImageProbe(source_a, 640, 480),
            ImageProbe(source_b, 640, 480),
        ),
    )
    settings = RemoteIqaSettings(
        "http://127.0.0.1:8765",
        (RemoteIqaStorageRoot("shared", "C:/shared"),),
        "shared",
    )

    def resolve(path: Path | str, _settings: RemoteIqaSettings) -> ResolvedSource:
        source = Path(path)
        digest = "a" * 64 if source.name == "a.png" else "b" * 64
        return ResolvedSource(
            LogicalStoragePath("shared", f"fixture/{source.name}"),
            digest,
            source,
            False,
        )

    monkeypatch.setattr(submission, "resolve_or_stage_source", resolve)

    payload = json.loads(format_request_json(entries, settings, "current_pair"))

    assert payload == {
        "submission_kind": "current_pair",
        "variants": [{"variant_id": "A"}, {"variant_id": "B"}],
        "scenes": [
            {
                "scene_id": "scene_000000",
                "sources": [
                    {
                        "variant_id": "A",
                        "storage_root_id": "shared",
                        "relative_path": "fixture/a.png",
                        "sha256": "a" * 64,
                        "width": 640,
                        "height": 480,
                    },
                    {
                        "variant_id": "B",
                        "storage_root_id": "shared",
                        "relative_path": "fixture/b.png",
                        "sha256": "b" * 64,
                        "width": 640,
                        "height": 480,
                    },
                ],
            }
        ],
    }
    serialized = json.dumps(payload)
    assert "127.0.0.1" not in serialized
    assert "C:/shared" not in serialized
    assert str(tmp_path) not in serialized
