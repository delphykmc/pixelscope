# PixelScope evaluation API v1

All production endpoints require HTTPS and schema-version compatibility.

- `POST /v1/jobs` creates a job and returns its ID.
- `GET /v1/jobs/{job_id}` returns queued/running/succeeded/failed/cancelled.
- `GET /v1/jobs/{job_id}/result` returns model/preprocessing metadata, scalar
  metrics, artifacts, elapsed time, and structured errors.
- `POST /v1/jobs/{job_id}/cancel` requests cancellation.

Future clients use bounded retries with exponential backoff, finite timeouts,
upload/download cancellation, maximum-size checks, input SHA-256 deduplication,
and a local result cache. Server URL and bearer/internal credentials belong in
external user configuration/credential storage. Never log tokens, image content,
or unnecessary sensitive paths; TLS certificate verification may not be disabled.
