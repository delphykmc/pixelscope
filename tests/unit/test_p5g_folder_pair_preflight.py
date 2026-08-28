from __future__ import annotations

from pixelscope.remote import iqa_client, iqa_submission
from scripts import p5g_folder_pair_preflight


class _FolderPairClient(iqa_client.IqaJobClient):
    def __init__(self, status_states: list[iqa_submission.JobState]) -> None:
        self.status_states = list(status_states)
        self.create_calls = 0
        self.status_calls = 0
        self.result_calls = 0
        self.cancel_calls = 0

    def create_job(
        self,
        request: iqa_submission.IqaJobRequest,
    ) -> iqa_submission.IqaJobCreated:
        self.create_calls += 1
        return iqa_submission.IqaJobCreated("folder-job-1", iqa_submission.JobState.QUEUED)

    def get_status(self, job_id: str) -> iqa_submission.IqaJobStatus:
        self.status_calls += 1
        state = self.status_states.pop(0)
        return iqa_submission.IqaJobStatus(
            job_id,
            state,
            0,
            3,
            "preflight source verification passed",
        )

    def get_result(self, job_id: str) -> iqa_submission.IqaResultReference:
        self.result_calls += 1
        raise iqa_client.IqaClientError(
            iqa_client.IqaClientErrorKind.HTTP,
            "HTTP 409",
            status_code=409,
        )

    def cancel_job(self, job_id: str) -> iqa_submission.IqaJobStatus:
        self.cancel_calls += 1
        return iqa_submission.IqaJobStatus(
            job_id,
            iqa_submission.JobState.CANCELLED,
            0,
            3,
            "cancel observed",
        )


def _folder_request(scene_count: int = 3) -> iqa_submission.IqaJobRequest:
    scenes: list[iqa_submission.SceneRequest] = []
    for index in range(scene_count):
        source_a = iqa_submission.PortableSourceRequest(
            "iqadata",
            f"project/A/image_{index:02d}.png",
            f"{index + 1:064x}",
            1920,
            1080,
        )
        source_b = iqa_submission.PortableSourceRequest(
            "iqadata",
            f"project/B/image_{index:02d}.png",
            f"{index + 101:064x}",
            1920,
            1080,
        )
        scenes.append(
            iqa_submission.SceneRequest(
                f"scene_{index:06d}",
                (("A", source_a), ("B", source_b)),
            )
        )
    return iqa_submission.IqaJobRequest(
        "folder_pair",
        ("A", "B"),
        tuple(scenes),
    )


def _current_request() -> iqa_submission.IqaJobRequest:
    request = _folder_request(1)
    return iqa_submission.IqaJobRequest(
        "current_pair",
        request.variants,
        request.scenes,
    )


def _check_status(
    report: p5g_folder_pair_preflight.FolderPairPreflightReport,
    name: str,
) -> str:
    return next(check.status for check in report.request_checks if check.name == name)


def test_multi_scene_folder_pair_delegates_to_existing_p5g_lifecycle() -> None:
    client = _FolderPairClient(
        [
            iqa_submission.JobState.PREPARING,
            iqa_submission.JobState.FAILED,
            iqa_submission.JobState.FAILED,
            iqa_submission.JobState.FAILED,
        ]
    )

    report = p5g_folder_pair_preflight.run_folder_pair_preflight_validation(
        client,
        _folder_request(),
        expected_scene_count=3,
        required_terminal_message_substring="source verification passed",
    )

    assert report.passed
    assert report.request_scene_count == 3
    assert report.request_source_count == 6
    assert report.distinct_storage_root_count == 1
    assert _check_status(report, "folder_pair_submission_kind") == "PASS"
    assert _check_status(report, "folder_pair_multi_scene") == "PASS"
    assert _check_status(report, "folder_pair_ab_shape") == "PASS"
    assert _check_status(report, "expected_scene_count") == "PASS"
    assert report.lifecycle is not None
    assert report.lifecycle.terminal_state == "failed"
    assert report.lifecycle.terminal_stability_states == ("failed", "failed")
    assert report.lifecycle.result.http_status == 409
    assert client.create_calls == 1
    assert client.result_calls == 1


def test_folder_pair_preflight_rejects_current_pair_before_create() -> None:
    client = _FolderPairClient([])

    report = p5g_folder_pair_preflight.run_folder_pair_preflight_validation(
        client,
        _current_request(),
    )

    assert not report.passed
    assert report.lifecycle is None
    assert _check_status(report, "folder_pair_submission_kind") == "FAIL"
    assert client.create_calls == 0


def test_folder_pair_preflight_requires_multiple_scenes_before_create() -> None:
    client = _FolderPairClient([])

    report = p5g_folder_pair_preflight.run_folder_pair_preflight_validation(
        client,
        _folder_request(1),
    )

    assert not report.passed
    assert report.lifecycle is None
    assert _check_status(report, "folder_pair_multi_scene") == "FAIL"
    assert client.create_calls == 0


def test_folder_pair_preflight_rejects_unexpected_scene_count_before_create() -> None:
    client = _FolderPairClient([])

    report = p5g_folder_pair_preflight.run_folder_pair_preflight_validation(
        client,
        _folder_request(),
        expected_scene_count=2,
    )

    assert not report.passed
    assert report.lifecycle is None
    assert _check_status(report, "expected_scene_count") == "FAIL"
    assert client.create_calls == 0
