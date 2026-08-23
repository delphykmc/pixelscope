from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pixelscope.remote.iqa_client import HttpIqaJobClient
from pixelscope.remote.iqa_compatibility_probe import run_iqa_compatibility_probe
from pixelscope.remote.iqa_submission import (
    IqaJobRequest,
    PortableSourceRequest,
    SceneRequest,
)


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_positive_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _parse_source(data: object) -> tuple[str, PortableSourceRequest]:
    if not isinstance(data, dict):
        raise ValueError("Scene source must be an object")
    variant_id = _required_string(data, "variant_id")
    source = PortableSourceRequest(
        storage_root_id=_required_string(data, "storage_root_id"),
        relative_path=_required_string(data, "relative_path"),
        sha256=_required_string(data, "sha256"),
        width=_required_positive_int(data, "width"),
        height=_required_positive_int(data, "height"),
    )
    return variant_id, source


def _parse_request(path: Path) -> IqaJobRequest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("request JSON must be an object")
    raw_variants = raw.get("variants")
    if not isinstance(raw_variants, list):
        raise ValueError("variants must be an array")
    variants = tuple(
        _required_string(item, "variant_id")
        if isinstance(item, dict)
        else (_ for _ in ()).throw(ValueError("variant must be an object"))
        for item in raw_variants
    )
    raw_scenes = raw.get("scenes")
    if not isinstance(raw_scenes, list):
        raise ValueError("scenes must be an array")
    scenes: list[SceneRequest] = []
    for item in raw_scenes:
        if not isinstance(item, dict):
            raise ValueError("Scene must be an object")
        raw_sources = item.get("sources")
        if not isinstance(raw_sources, list):
            raise ValueError("Scene sources must be an array")
        scenes.append(
            SceneRequest(
                scene_id=_required_string(item, "scene_id"),
                sources=tuple(_parse_source(source) for source in raw_sources),
            )
        )
    return IqaJobRequest(
        submission_kind=_required_string(raw, "submission_kind"),
        variants=variants,
        scenes=tuple(scenes),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded P5-F Remote IQA transport compatibility probe.",
    )
    parser.add_argument("server_base_url")
    parser.add_argument("request_json", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.2)
    parser.add_argument("--max-status-requests", type=int, default=64)
    parser.add_argument("--cancel-after-status-requests", type=int)
    args = parser.parse_args()
    if args.poll_interval_seconds < 0.0:
        parser.error("--poll-interval-seconds must be non-negative")

    request = _parse_request(args.request_json)
    client = HttpIqaJobClient(
        args.server_base_url,
        timeout_seconds=args.timeout_seconds,
    )
    try:
        trace = run_iqa_compatibility_probe(
            client,
            request,
            max_status_requests=args.max_status_requests,
            cancel_after_status_requests=args.cancel_after_status_requests,
            poll_pause=lambda: time.sleep(args.poll_interval_seconds),
        )
    finally:
        client.close()

    # The trace intentionally excludes server URL, request body, credentials, and source content.
    print(json.dumps(asdict(trace), ensure_ascii=False, indent=2))
    return 2 if trace.error_kind is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
