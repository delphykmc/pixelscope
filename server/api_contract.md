# Historical pre-P5 evaluation API v1 scaffold

Status: **Historical / unsupported**

This file records the initial-release API sketch that accompanied the removed
`evaluation_client.py`, `mock_client.py`, and `schemas.py` scaffold. No production code
used this contract, and canonical P5 uses `/v1/iqa/jobs` with the durable authority in
[`../docs/REMOTE_IQA_CONTRACT.md`](../docs/REMOTE_IQA_CONTRACT.md). The endpoint sketch
below is preserved as history only; it must not be implemented or consumed as a current
PixelScope contract.

All production endpoints require HTTPS and schema-version compatibility.

- `POST /v1/jobs` creates a job and returns its ID.
- `GET /v1/jobs/{job_id}` returns queued/running/succeeded/failed/cancelled.
- `GET /v1/jobs/{job_id}/result` returns model/preprocessing metadata, scalar
  metrics, artifacts, elapsed time, and structured errors.
- `POST /v1/jobs/{job_id}/cancel` requests cancellation.

The initial sketch anticipated bounded retries with exponential backoff, finite timeouts,
upload/download cancellation, maximum-size checks, input SHA-256 deduplication,
and a local result cache. Server URL and bearer/internal credentials belong in
external user configuration/credential storage. Never log tokens, image content,
or unnecessary sensitive paths; TLS certificate verification may not be disabled.
