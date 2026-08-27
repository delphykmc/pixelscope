from __future__ import annotations

from pixelscope.remote.iqa_client import IqaClientError, IqaClientErrorKind, IqaJobClient
from pixelscope.remote.iqa_submission import (
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
    IqaResultReference,
    JobState,
    PortableSourceRequest,
    SceneRequest,
)
from scripts.p5g_iqa_preflight import run_p5g_preflight_validation


class _PreflightClient(IqaJobClient):
    def __init__(
        self,
        status_states: list[JobState],
        *,
        cancel_state: JobState = JobState.CANCELLED,
        result_status: int = 409,
        published_result: IqaResultReference | None = None,
    ) -> None:
        self.status_states = list(status_states)
        self.cancel_state = cancel_state
        self.result_status = result_status
        self.published_result = published_result
        self.create_calls = 0
        self.status_calls = 0
        self.cancel_calls = 0
        self.result_calls = 0

    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        self.create_calls += 1
        return IqaJobCreated("job-1", JobState.QUEUED)

    def get_status(self, job_id: str) -> IqaJobStatus:
        self.status_calls += 1
        state = self.status_states.pop(0)
        return IqaJobStatus(job_id, state, 0, 1, "preflight source verification passed")

    def get_result(self, job_id: str) -> IqaResultReference:
        self.result_calls += 1
        if self.published_result is not None:
            return self.published_result
        raise IqaClientError(
            IqaClientErrorKind.HTTP,
            f"HTTP {self.result_status}",
            status_code=self.result_status,
        )

    def cancel_job(self, job_id: str) -> IqaJobStatus:
        self.cancel_calls += 1
        return IqaJobStatus(job_id, self.cancel_state, 0, 1, "cancel observed")


def _request(relative_path: str = "project/A/image.png") -> IqaJobRequest:
    source_a = PortableSourceRequest(
        "iqadata",
        relative_path,
        "a" * 64,
        1920,
        1080,
    )
    source_b = PortableSourceRequest(
        "iqadata",
        "project/B/image.png",
        "b" * 64,
        1920,
        1080,
    )
    return IqaJobRequest(
        "current_pair",
        ("A", "B"),
        (SceneRequest("scene_000000", (("A", source_a), ("B", source_b))),),
    )


def _check_status(report: object, name: str) -> str:
    checks = getattr(report, "checks")
    return next(check.status for check in checks if check.name == name)


def test_failed_preflight_requires_stable_terminal_and_unpublished_result() -> None:
    client = _PreflightClient(
        [JobState.PREPARING, JobState.FAILED, JobState.FAILED, JobState.FAILED]
    )

    report = run_p5g_preflight_validation(
        client,
        _request(),
        mode="failed",
        required_terminal_message_substring="source verification passed",
    )

    assert report.passed
    assert report.terminal_state == "failed"
    assert report.terminal_stability_states == ("failed", "failed")
    assert report.result.fetch_attempted
    assert not report.result.reference_seen
    assert report.result.http_status == 409
    assert report.result.schema_version is None
    assert report.result.publication_state is None
    assert _check_status(report, "terminal_message_evidence") == "PASS"
    assert _check_status(report, "result_not_published") == "PASS"
    assert client.result_calls == 1


def test_cancel_preflight_accepts_cancelled_and_rechecks_terminal_state() -> None:
    client = _PreflightClient(
        [JobState.PREPARING, JobState.CANCELLED, JobState.CANCELLED],
        cancel_state=JobState.CANCELLED,
    )

    report = run_p5g_preflight_validation(client, _request(), mode="cancel")

    assert report.passed
    assert report.terminal_state == "cancelled"
    assert report.terminal_stability_states == ("cancelled", "cancelled")
    assert _check_status(report, "cancel_issued") == "PASS"
    assert _check_status(report, "expected_terminal_state") == "PASS"
    assert client.cancel_calls == 1


def test_preflight_rejects_result_publication_for_failed_job() -> None:
    reference = IqaResultReference(
        "job-1",
        "iqadata",
        "results/job-1",
        2,
        "complete",
    )
    client = _PreflightClient(
        [JobState.FAILED, JobState.FAILED, JobState.FAILED],
        published_result=reference,
    )

    report = run_p5g_preflight_validation(client, _request(), mode="failed")

    assert not report.passed
    assert report.result.fetch_attempted
    assert report.result.reference_seen
    assert report.result.schema_version == 2
    assert _check_status(report, "result_not_published") == "FAIL"


def test_preflight_rejects_terminal_state_that_is_not_stable() -> None:
    client = _PreflightClient(
        [JobState.FAILED, JobState.PREPARING, JobState.FAILED],
    )

    report = run_p5g_preflight_validation(client, _request(), mode="failed")

    assert not report.passed
    assert report.terminal_state == "failed"
    assert report.terminal_stability_states == ("preparing", "failed")
    assert _check_status(report, "terminal_state_stable") == "FAIL"


def test_preflight_rejects_nonportable_request_before_create() -> None:
    client = _PreflightClient([])

    report = run_p5g_preflight_validation(
        client,
        _request("../outside/image.png"),
        mode="failed",
    )

    assert not report.passed
    assert report.error_kind == "request"
    assert _check_status(report, "request_portable_identity") == "FAIL"
    assert client.create_calls == 0
