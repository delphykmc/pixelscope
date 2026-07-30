from __future__ import annotations

import json

from pixelscope.remote.mock_client import MockEvaluationClient
from pixelscope.remote.schemas import EvaluationRequest, EvaluationResult, JobState

HASH = "0123456789abcdef" * 4


def test_schema_round_trip() -> None:
    client = MockEvaluationClient()
    request = EvaluationRequest(model_id="quality-v1", input_sha256=HASH)
    job = client.create_job(request)
    result = client.get_result(job.job_id)
    restored = EvaluationResult.parse_raw(result.json())
    assert restored.input_sha256 == HASH
    assert restored.artifacts[0].inline_values is not None
    assert json.loads(result.json())["api_schema_version"] == "1.0"


def test_mock_is_deterministic_and_cancellable() -> None:
    client = MockEvaluationClient()
    request = EvaluationRequest(model_id="quality-v1", input_sha256=HASH)
    first = client.create_job(request)
    score_a = client.get_result(first.job_id).metrics[0].value
    second = client.create_job(request)
    score_b = client.get_result(second.job_id).metrics[0].value
    assert score_a == score_b
    assert client.cancel_job(second.job_id).state is JobState.CANCELLED
