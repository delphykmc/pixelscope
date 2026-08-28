from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from pixelscope.remote.iqa_client import HttpIqaJobClient, IqaJobClient
from pixelscope.remote.iqa_submission import IqaJobRequest
from scripts.p5f_iqa_probe import _parse_request
from scripts.p5g_iqa_preflight import (
    P5gPreflightReport,
    PreflightCheck,
    run_p5g_preflight_validation,
)


@dataclass(frozen=True)
class FolderPairPreflightReport:
    request_scene_count: int
    request_source_count: int
    distinct_storage_root_count: int
    expected_scene_count: int | None
    request_checks: tuple[PreflightCheck, ...]
    lifecycle: P5gPreflightReport | None

    @property
    def passed(self) -> bool:
        return (
            all(check.status != "FAIL" for check in self.request_checks)
            and self.lifecycle is not None
            and self.lifecycle.passed
        )


def run_folder_pair_preflight_validation(
    client: IqaJobClient,
    request: IqaJobRequest,
    *,
    expected_scene_count: int | None = None,
    mode: str = "failed",
    max_status_requests: int = 64,
    cancel_after_status_requests: int = 1,
    terminal_stability_requests: int = 2,
    allowed_result_http_statuses: frozenset[int] = frozenset({409}),
    required_terminal_message_substring: str | None = None,
    poll_pause: Callable[[], None] | None = None,
) -> FolderPairPreflightReport:
    """Validate a real multi-Scene Folder Pair request before exercising P5-G lifecycle."""

    if expected_scene_count is not None and expected_scene_count < 2:
        raise ValueError("expected_scene_count must be at least 2 for multi-Scene preflight")

    scene_count = len(request.scenes)
    source_count = sum(len(scene.sources) for scene in request.scenes)
    root_count = len(
        {
            source.storage_root_id
            for scene in request.scenes
            for _variant_id, source in scene.sources
        }
    )
    request_checks = _folder_pair_request_checks(request, expected_scene_count)
    if any(check.status == "FAIL" for check in request_checks):
        return FolderPairPreflightReport(
            scene_count,
            source_count,
            root_count,
            expected_scene_count,
            request_checks,
            None,
        )

    lifecycle = run_p5g_preflight_validation(
        client,
        request,
        mode=mode,
        max_status_requests=max_status_requests,
        cancel_after_status_requests=cancel_after_status_requests,
        terminal_stability_requests=terminal_stability_requests,
        allowed_result_http_statuses=allowed_result_http_statuses,
        required_terminal_message_substring=required_terminal_message_substring,
        poll_pause=poll_pause,
    )
    return FolderPairPreflightReport(
        scene_count,
        source_count,
        root_count,
        expected_scene_count,
        request_checks,
        lifecycle,
    )


def _folder_pair_request_checks(
    request: IqaJobRequest,
    expected_scene_count: int | None,
) -> tuple[PreflightCheck, ...]:
    checks = [
        PreflightCheck(
            "folder_pair_submission_kind",
            "PASS" if request.submission_kind == "folder_pair" else "FAIL",
        ),
        PreflightCheck(
            "folder_pair_multi_scene",
            "PASS" if len(request.scenes) >= 2 else "FAIL",
        ),
        PreflightCheck(
            "folder_pair_ab_shape",
            "PASS"
            if request.variants == ("A", "B")
            and all(
                tuple(variant_id for variant_id, _source in scene.sources) == ("A", "B")
                for scene in request.scenes
            )
            else "FAIL",
        ),
    ]
    if expected_scene_count is None:
        checks.append(PreflightCheck("expected_scene_count", "NOT_REQUESTED"))
    else:
        checks.append(
            PreflightCheck(
                "expected_scene_count",
                "PASS" if len(request.scenes) == expected_scene_count else "FAIL",
            )
        )
    return tuple(checks)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a production-generated multi-Scene Folder Pair request against the "
            "temporary P5-G external server without exposing server URLs, source paths, "
            "job IDs, or response message text."
        )
    )
    parser.add_argument("server_base_url")
    parser.add_argument("request_json", type=Path)
    parser.add_argument(
        "--expect-scene-count",
        type=int,
        help="Require the exact prepared Folder Pair Scene count; must be at least 2.",
    )
    parser.add_argument("--mode", choices=("failed", "cancel"), default="failed")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.2)
    parser.add_argument("--max-status-requests", type=int, default=64)
    parser.add_argument("--cancel-after-status-requests", type=int, default=1)
    parser.add_argument("--terminal-stability-requests", type=int, default=2)
    parser.add_argument(
        "--allowed-result-http-status",
        type=int,
        action="append",
        dest="allowed_result_http_statuses",
        help="Allowed HTTP status for unpublished failed/cancelled results; default: 409.",
    )
    parser.add_argument(
        "--require-terminal-message-substring",
        help=(
            "Require a case-insensitive token in the terminal message. The message itself is "
            "never printed."
        ),
    )
    args = parser.parse_args()
    if args.expect_scene_count is not None and args.expect_scene_count < 2:
        parser.error("--expect-scene-count must be at least 2")
    if args.timeout_seconds <= 0.0:
        parser.error("--timeout-seconds must be positive")
    if args.poll_interval_seconds < 0.0:
        parser.error("--poll-interval-seconds must be non-negative")

    request = _parse_request(args.request_json)
    client = HttpIqaJobClient(args.server_base_url, timeout_seconds=args.timeout_seconds)

    def pause() -> None:
        time.sleep(args.poll_interval_seconds)

    allowed_statuses = frozenset(args.allowed_result_http_statuses or [409])
    try:
        report = run_folder_pair_preflight_validation(
            client,
            request,
            expected_scene_count=args.expect_scene_count,
            mode=args.mode,
            max_status_requests=args.max_status_requests,
            cancel_after_status_requests=args.cancel_after_status_requests,
            terminal_stability_requests=args.terminal_stability_requests,
            allowed_result_http_statuses=allowed_statuses,
            required_terminal_message_substring=args.require_terminal_message_substring,
            poll_pause=pause,
        )
    finally:
        client.close()

    payload = asdict(report)
    payload["passed"] = report.passed
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
