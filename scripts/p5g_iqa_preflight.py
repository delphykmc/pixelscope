from __future__ import annotations

import argparse
import hashlib
import json
import string
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from pixelscope.remote.iqa_client import (
    HttpIqaJobClient,
    IqaClientError,
    IqaClientErrorKind,
    IqaJobClient,
)
from pixelscope.remote.iqa_storage import StorageResolutionError, validate_relative_path
from pixelscope.remote.iqa_submission import IqaJobRequest, JobState
from scripts.p5f_iqa_probe import _parse_request


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str


@dataclass(frozen=True)
class PreflightResultEvidence:
    fetch_attempted: bool
    reference_seen: bool
    http_status: int | None
    schema_version: int | None
    publication_state: str | None
    storage_root_id: str | None
    relative_path: str | None


@dataclass(frozen=True)
class P5gPreflightReport:
    mode: str
    job_id_fingerprint: str | None
    request_scene_count: int
    request_source_count: int
    distinct_storage_root_count: int
    state_sequence: tuple[str, ...]
    terminal_state: str | None
    terminal_stability_states: tuple[str, ...]
    terminal_message_present: bool
    terminal_message_length: int | None
    result: PreflightResultEvidence
    checks: tuple[PreflightCheck, ...]
    error_kind: str | None
    error_message: str | None

    @property
    def passed(self) -> bool:
        return self.error_kind is None and all(check.status != "FAIL" for check in self.checks)


def run_p5g_preflight_validation(
    client: IqaJobClient,
    request: IqaJobRequest,
    *,
    mode: str = "failed",
    max_status_requests: int = 64,
    cancel_after_status_requests: int = 1,
    terminal_stability_requests: int = 2,
    allowed_result_http_statuses: frozenset[int] = frozenset({409}),
    required_terminal_message_substring: str | None = None,
    poll_pause: Callable[[], None] | None = None,
) -> P5gPreflightReport:
    if mode not in {"failed", "cancel"}:
        raise ValueError("mode must be 'failed' or 'cancel'")
    if max_status_requests < 1:
        raise ValueError("max_status_requests must be positive")
    if cancel_after_status_requests < 1:
        raise ValueError("cancel_after_status_requests must be positive")
    if terminal_stability_requests < 1:
        raise ValueError("terminal_stability_requests must be positive")
    if not allowed_result_http_statuses:
        raise ValueError("at least one allowed result HTTP status is required")

    checks: list[PreflightCheck] = []
    states: list[str] = []
    stability_states: list[str] = []
    job_id: str | None = None
    terminal_state: JobState | None = None
    terminal_message: str | None = None
    result_evidence = PreflightResultEvidence(False, False, None, None, None, None, None)

    scene_count, source_count, root_count = _request_shape(request)
    try:
        _validate_portable_request(request)
    except (StorageResolutionError, ValueError):
        checks.append(PreflightCheck("request_portable_identity", "FAIL"))
        return _report(
            mode,
            job_id,
            scene_count,
            source_count,
            root_count,
            states,
            terminal_state,
            stability_states,
            terminal_message,
            result_evidence,
            checks,
            "request",
            "request portability validation failed",
        )
    checks.append(PreflightCheck("request_portable_identity", "PASS"))

    expected_terminal = JobState.FAILED if mode == "failed" else JobState.CANCELLED
    cancel_issued = False
    try:
        created = client.create_job(request)
        job_id = created.job_id
        states.append(created.state.value)
        checks.append(PreflightCheck("create_nonterminal", "PASS"))

        status_requests = 0
        observed_state = created.state
        while not observed_state.terminal and status_requests < max_status_requests:
            if poll_pause is not None:
                poll_pause()
            status = client.get_status(job_id)
            status_requests += 1
            observed_state = status.state
            terminal_message = status.message
            states.append(status.state.value)

            if (
                mode == "cancel"
                and not cancel_issued
                and status_requests >= cancel_after_status_requests
                and not observed_state.terminal
            ):
                cancel_status = client.cancel_job(job_id)
                cancel_issued = True
                observed_state = cancel_status.state
                terminal_message = cancel_status.message
                states.append(cancel_status.state.value)

        if mode == "cancel":
            checks.append(PreflightCheck("cancel_issued", "PASS" if cancel_issued else "FAIL"))

        if not observed_state.terminal:
            checks.append(PreflightCheck("terminal_reached", "FAIL"))
            return _report(
                mode,
                job_id,
                scene_count,
                source_count,
                root_count,
                states,
                None,
                stability_states,
                terminal_message,
                result_evidence,
                checks,
                "status_limit",
                "status request limit reached before terminal state",
            )

        terminal_state = observed_state
        checks.extend(
            (
                PreflightCheck("status_job_identity", "PASS"),
                PreflightCheck("canonical_state_parsing", "PASS"),
                PreflightCheck("progress_contract", "PASS"),
                PreflightCheck("terminal_reached", "PASS"),
                PreflightCheck(
                    "expected_terminal_state",
                    "PASS" if terminal_state is expected_terminal else "FAIL",
                ),
            )
        )

        for _ in range(terminal_stability_requests):
            if poll_pause is not None:
                poll_pause()
            status = client.get_status(job_id)
            stability_states.append(status.state.value)
            if status.message is not None:
                terminal_message = status.message
        checks.append(
            PreflightCheck(
                "terminal_state_stable",
                "PASS"
                if all(state == terminal_state.value for state in stability_states)
                else "FAIL",
            )
        )

        if terminal_message is None:
            checks.append(PreflightCheck("terminal_message_bounded", "PASS"))
        else:
            checks.append(
                PreflightCheck(
                    "terminal_message_bounded",
                    "PASS" if len(terminal_message) <= 512 else "FAIL",
                )
            )

        if required_terminal_message_substring is None:
            checks.append(PreflightCheck("server_preflight_message_evidence", "NOT_REQUESTED"))
        else:
            message_match = (
                terminal_message is not None
                and required_terminal_message_substring.casefold() in terminal_message.casefold()
            )
            checks.append(
                PreflightCheck(
                    "server_preflight_message_evidence",
                    "PASS" if message_match else "FAIL",
                )
            )

        result_evidence = _verify_result_not_published(client, job_id)
        checks.append(
            PreflightCheck(
                "result_not_published",
                "PASS"
                if result_evidence.fetch_attempted
                and not result_evidence.reference_seen
                and result_evidence.http_status in allowed_result_http_statuses
                else "FAIL",
            )
        )
    except IqaClientError as error:
        return _report(
            mode,
            job_id,
            scene_count,
            source_count,
            root_count,
            states,
            terminal_state,
            stability_states,
            terminal_message,
            result_evidence,
            checks,
            error.kind.value,
            _safe_error_message(error),
        )

    return _report(
        mode,
        job_id,
        scene_count,
        source_count,
        root_count,
        states,
        terminal_state,
        stability_states,
        terminal_message,
        result_evidence,
        checks,
        None,
        None,
    )


def _verify_result_not_published(
    client: IqaJobClient,
    job_id: str,
) -> PreflightResultEvidence:
    try:
        reference = client.get_result(job_id)
    except IqaClientError as error:
        if error.kind is not IqaClientErrorKind.HTTP:
            raise
        return PreflightResultEvidence(
            True,
            False,
            error.status_code,
            None,
            None,
            None,
            None,
        )

    return PreflightResultEvidence(
        True,
        True,
        None,
        reference.schema_version,
        reference.publication_state,
        "<redacted>",
        "<redacted>",
    )


def _validate_portable_request(request: IqaJobRequest) -> None:
    if not request.scenes:
        raise ValueError("request must contain at least one Scene")
    for scene in request.scenes:
        for _variant_id, source in scene.sources:
            validate_relative_path(source.relative_path)
            invalid_sha = len(source.sha256) != 64 or any(
                char not in string.hexdigits for char in source.sha256
            )
            if invalid_sha:
                raise ValueError("source sha256 must be a 64-character hexadecimal digest")
            if source.width <= 0 or source.height <= 0:
                raise ValueError("source dimensions must be positive")


def _request_shape(request: IqaJobRequest) -> tuple[int, int, int]:
    sources = [source for scene in request.scenes for _variant_id, source in scene.sources]
    return len(request.scenes), len(sources), len({source.storage_root_id for source in sources})


def _job_id_fingerprint(job_id: str | None) -> str | None:
    if job_id is None:
        return None
    return hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:12]


def _safe_error_message(error: IqaClientError) -> str:
    if error.status_code is not None:
        return f"HTTP {error.status_code}"
    return error.kind.value


def _report(
    mode: str,
    job_id: str | None,
    scene_count: int,
    source_count: int,
    root_count: int,
    states: list[str],
    terminal_state: JobState | None,
    stability_states: list[str],
    terminal_message: str | None,
    result: PreflightResultEvidence,
    checks: list[PreflightCheck],
    error_kind: str | None,
    error_message: str | None,
) -> P5gPreflightReport:
    return P5gPreflightReport(
        mode=mode,
        job_id_fingerprint=_job_id_fingerprint(job_id),
        request_scene_count=scene_count,
        request_source_count=source_count,
        distinct_storage_root_count=root_count,
        state_sequence=tuple(states),
        terminal_state=terminal_state.value if terminal_state is not None else None,
        terminal_stability_states=tuple(stability_states),
        terminal_message_present=terminal_message is not None,
        terminal_message_length=len(terminal_message) if terminal_message is not None else None,
        result=result,
        checks=tuple(checks),
        error_kind=error_kind,
        error_message=error_message,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the P5-G external preflight lifecycle without exposing server URLs, "
            "request paths, job IDs, or response message text in the report."
        )
    )
    parser.add_argument("server_base_url")
    parser.add_argument("request_json", type=Path)
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
        report = run_p5g_preflight_validation(
            client,
            request,
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
