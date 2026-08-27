# Temporary PixelScope IQA Preflight Server — Self-contained Implementation Request

## 0. Read this first

You are being asked to **design and write the code for a small temporary HTTP server**.

Assume you know nothing about PixelScope, its repository, its development phases, or any previous conversations. Everything you need is in this document.

You also have **no Git connector, no terminal, and no ability to read or modify local files**. Therefore:

- do not say that you created, edited, committed, or tested files;
- do not ask to inspect a repository;
- do not ask for earlier PixelScope documents or Phase history;
- do not depend on files that are not described here;
- instead, produce the implementation in the normal chat style used when the user must create files manually;
- show the project tree first;
- then show the **complete contents of every required file** in separate code blocks;
- then show dependency-install, run, curl/manual-check, and pytest commands;
- if a correction is requested later, return the complete replacement content of each changed file rather than an inaccessible patch.

The output should be directly usable by an engineer who will manually create the files on an internal server.

---

# 1. Goal

Build a **temporary external preflight server** for a Windows desktop application named PixelScope.

PixelScope will eventually submit image pairs to a real GPU-based IQA service. That IQA algorithm does **not** exist in this temporary project.

The purpose of this temporary server is only to prove that the following real integration path works:

```text
PixelScope on Windows
    |
    | HTTP
    v
Temporary preflight server
    |
    | storage_root_id + relative_path
    v
Server-side shared-storage mount
    |
    v
Actual image bytes
```

The temporary server must validate:

1. Windows client -> server network connectivity;
2. exact REST request/response compatibility;
3. create -> status polling lifecycle;
4. cancellation;
5. server-side mapping of a logical storage root;
6. server read access to the submitted files;
7. SHA-256 agreement between client metadata and server-visible bytes;
8. image width/height agreement.

After those checks succeed, the job must deliberately end as `failed` because IQA computation is not implemented.

The server must **not fabricate a successful IQA result** merely to make the client appear to pass.

---

# 2. Required implementation style

Use a small, readable Python project.

Recommended fixed stack:

- Python 3.10 or newer;
- FastAPI;
- Uvicorn;
- Pydantic models through FastAPI;
- Pillow only for image dimension validation;
- pytest;
- httpx/FastAPI TestClient for tests.

Keep the implementation intentionally small. This is a temporary integration server, not production infrastructure.

Do not add:

- database;
- Redis;
- Celery;
- message broker;
- GPU framework;
- Docker/Kubernetes requirement;
- authentication/SSO;
- WebSocket;
- production queue architecture.

An in-memory job registry plus a background thread/task is sufficient.

---

# 3. Required project deliverable

Design a compact project approximately like this:

```text
pixelscope_iqa_preflight/
  README.md
  requirements.txt
  app/
    __init__.py
    main.py
    models.py
    settings.py
    jobs.py
    storage.py
  tests/
    test_api.py
    test_storage.py
```

You may adjust the exact file split if there is a concrete technical reason, but keep it similarly small.

Your answer must include the **entire content** of every file needed to run and test the server.

---

# 4. Canonical HTTP API

PixelScope uses exactly these endpoints:

```text
POST /v1/iqa/jobs
GET  /v1/iqa/jobs/{job_id}
GET  /v1/iqa/jobs/{job_id}/result
POST /v1/iqa/jobs/{job_id}/cancel
```

Also implement this operational endpoint:

```text
GET /health
```

`/health` is only for server/operator checks. PixelScope does not depend on it.

All API payloads are JSON objects.

---

# 5. Exact create-job request

PixelScope sends this JSON shape:

```json
{
  "submission_kind": "current_pair",
  "variants": [
    {"variant_id": "A"},
    {"variant_id": "B"}
  ],
  "scenes": [
    {
      "scene_id": "scene_000000",
      "sources": [
        {
          "variant_id": "A",
          "storage_root_id": "iqadata",
          "relative_path": "project42/A/image_0001.png",
          "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          "width": 1920,
          "height": 1080
        },
        {
          "variant_id": "B",
          "storage_root_id": "iqadata",
          "relative_path": "project42/B/image_0001.png",
          "sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
          "width": 1920,
          "height": 1080
        }
      ]
    }
  ]
}
```

## Request rules

The server must validate all of the following:

- `submission_kind` is a non-empty string. Treat its value as opaque; do not invent behavior based on it.
- `variants` must be exactly:

```json
[
  {"variant_id": "A"},
  {"variant_id": "B"}
]
```

- request contains between 1 and 512 scenes inclusive;
- scene IDs must be deterministic, contiguous, and ordered:
  - `scene_000000`
  - `scene_000001`
  - `scene_000002`
  - ...
- every scene must contain exactly two sources in this exact order:
  - first `variant_id = "A"`
  - second `variant_id = "B"`
- every source contains:
  - `variant_id`
  - `storage_root_id`
  - `relative_path`
  - `sha256`
  - `width`
  - `height`
- there is **no `source_id` field** in this request contract;
- `width` and `height` must be positive integers;
- `sha256` must be exactly 64 hexadecimal characters;
- the A and B sources inside a scene must declare equal width and height;
- currently expected source file extensions are `.png`, `.jpg`, `.jpeg`, and `.bmp`.

Do not add temporary fields to this request such as `test_mode`, `delay_seconds`, `force_failure`, or server-local paths.

Test controls belong in server configuration, not in the API contract.

Malformed request structure should return HTTP 4xx and must not create a job.

---

# 6. Create-job response

For a valid request, create a unique job and return immediately.

Required example:

```json
{
  "job_id": "job_preflight_000001",
  "state": "queued"
}
```

Rules:

- `job_id` must be non-empty;
- maximum 128 characters;
- do not include `/`, `\\`, or NUL;
- create response must be non-terminal;
- use `queued` for the initial state;
- do not perform slow storage verification before returning the create response.

The background worker should perform storage verification after the job has been accepted.

---

# 7. Job states

PixelScope understands these exact state strings:

```text
queued
preparing
extracting
aggregating
writing
succeeded
partial
failed
cancelled
```

Terminal states are:

```text
succeeded
partial
failed
cancelled
```

This temporary server should normally use only:

```text
queued
preparing
failed
cancelled
```

Do not pretend to perform IQA by moving through `extracting`, `aggregating`, or `writing`.

Do not produce `succeeded` or `partial` because no actual IQA result is generated.

---

# 8. Normal temporary-server lifecycle

The intended lifecycle is:

```text
POST /v1/iqa/jobs
    |
    v
queued
    |
    v
preparing
    |
    +--> validate logical storage-root mapping
    +--> validate contained relative path
    +--> open actual image file read-only
    +--> stream SHA-256
    +--> compare expected SHA-256
    +--> read actual image dimensions
    +--> compare expected width/height
    |
    v
failed
```

If every preflight check succeeded, use a bounded message such as:

```text
preflight source verification passed; IQA computation is not implemented
```

This `failed` state is intentional and means the temporary server reached the boundary where the future IQA implementation would begin.

If preflight itself fails, use a short non-sensitive reason, for example:

```text
source verification failed: unknown storage root
source verification failed: file not found
source verification failed: SHA-256 mismatch
source verification failed: image dimensions mismatch
source verification failed: invalid relative path
```

Do not expose full local filesystem paths or Python stack traces in the client-facing status message.

---

# 9. Status endpoint

Endpoint:

```text
GET /v1/iqa/jobs/{job_id}
```

Non-terminal example:

```json
{
  "job_id": "job_preflight_000001",
  "state": "preparing",
  "completed_scenes": 0,
  "total_scenes": 1,
  "message": "validating shared-storage sources"
}
```

Intentional terminal example after successful preflight:

```json
{
  "job_id": "job_preflight_000001",
  "state": "failed",
  "completed_scenes": 0,
  "total_scenes": 1,
  "message": "preflight source verification passed; IQA computation is not implemented"
}
```

Rules:

- returned `job_id` must exactly equal the requested job ID;
- `state` must be one of the canonical state strings;
- `completed_scenes` and `total_scenes` must be non-negative integers;
- `completed_scenes <= total_scenes`;
- keep `message` short;
- status for a terminal job must remain stable during the lifetime of the process;
- unknown job ID should return HTTP 404 with a small JSON error.

For this temporary server it is acceptable to use `completed_scenes = 0` throughout because no IQA scene has actually been computed.

---

# 10. Cancellation

Endpoint:

```text
POST /v1/iqa/jobs/{job_id}/cancel
```

Cancellation must be observable while a job is still `queued` or `preparing`.

Implement a server-side configurable hold interval so the operator can reliably test cancellation.

Recommended environment variable:

```text
PIXELSCOPE_PREFLIGHT_HOLD_SECONDS=3.0
```

The worker should check cancellation during this hold and between source-verification operations.

Direct cancellation response:

```json
{
  "job_id": "job_preflight_000001",
  "state": "cancelled",
  "completed_scenes": 0,
  "total_scenes": 1,
  "message": "cancelled"
}
```

After cancellation:

- subsequent status requests must continue to return `cancelled`;
- the background worker must not later overwrite the job as `failed`;
- unknown job ID should return HTTP 404.

Cancelling an already terminal job may simply return its current terminal state.

---

# 11. Result endpoint

Endpoint:

```text
GET /v1/iqa/jobs/{job_id}/result
```

This temporary server does **not** publish an IQA result.

Therefore this endpoint must never fabricate a success response.

For an existing job with no published result, return HTTP 409:

```json
{
  "detail": "result is not published"
}
```

For an unknown job ID, return HTTP 404.

Do not create fake schema-v2 results, fake result directories, fake metrics, fake NPZ files, fake manifests, or fake publication state.

The client normally calls the result endpoint only after `succeeded` or `partial`, which this temporary server never emits.

---

# 12. Shared-storage configuration

PixelScope does not send the server's physical filesystem path.

It sends:

```text
storage_root_id + relative_path
```

Example portable identity:

```text
storage_root_id = iqadata
relative_path   = project42/A/image_0001.png
```

The server must map the logical root ID to a server-local mount path.

Use an environment variable containing JSON, for example:

```text
PIXELSCOPE_STORAGE_ROOTS_JSON={"iqadata":"/mnt/iqadata"}
```

On a Windows-hosted test server an equivalent value may be:

```text
PIXELSCOPE_STORAGE_ROOTS_JSON={"iqadata":"D:/shared/iqadata"}
```

The mapping is deployment configuration and must not be embedded into request identity.

At startup:

- parse the environment variable;
- require a JSON object mapping non-empty logical IDs to non-empty physical directory paths;
- resolve/normalize the configured root paths;
- fail startup clearly if configuration is malformed;
- document whether a configured-but-missing root is rejected at startup or when first used.

Never log credentials or secret values. There are no credentials in this temporary API contract.

---

# 13. Safe relative-path rules

`relative_path` is a portable POSIX-style relative path.

Valid example:

```text
project42/A/image_0001.png
```

Reject values that are:

- empty;
- longer than 2048 characters;
- contain NUL;
- absolute POSIX paths;
- Windows absolute paths;
- contain a drive prefix such as `C:`;
- contain backslashes;
- contain `.` or `..` path components;
- resolve outside the configured storage root.

The implementation must prevent traversal such as:

```text
../secret.txt
folder/../../secret.txt
C:/secret.txt
\\server\share\secret.txt
```

When resolving:

1. validate the portable relative path;
2. combine it with the configured physical root;
3. resolve the candidate path;
4. verify the resolved candidate is still contained under the resolved root;
5. require a regular readable file;
6. reject obvious symlink/escape cases rather than following a path outside the logical root.

Do not modify, rename, delete, chmod, or rewrite submitted image files.

---

# 14. Source-byte verification

For every submitted source, independently verify the bytes visible to the server.

## SHA-256

Compute SHA-256 in chunks, not by loading an entire image into memory. A 1 MiB chunk is reasonable.

Compare against the lowercase hexadecimal digest supplied in the request.

If it differs, terminal-fail the job with:

```text
source verification failed: SHA-256 mismatch
```

Do not include the physical path in the client-facing message.

## Dimensions

Open the image using Pillow only to inspect dimensions.

Compare the actual image `(width, height)` with the request metadata.

If they differ, terminal-fail with:

```text
source verification failed: image dimensions mismatch
```

Do not resize, decode for IQA, normalize, or otherwise process image content.

## A/B pair

The server must reject request metadata where A/B dimensions differ within a scene.

---

# 15. Background execution and thread safety

`POST /v1/iqa/jobs` must return promptly.

After creating the job:

- store it in an in-memory registry;
- start one background worker for the job;
- worker changes state from `queued` to `preparing`;
- worker performs the optional hold interval and storage checks;
- worker checks a cancellation flag repeatedly;
- worker finishes as either `cancelled` or `failed`;
- terminal state must never be overwritten later.

Protect shared job state with a lock or another clearly correct synchronization mechanism.

The project does not need high-throughput scheduling. Correctness and observability are more important than throughput.

A process restart may lose all jobs. Document that explicitly in README.

---

# 16. Job identity

Generate server-side IDs such as:

```text
job_preflight_000001
job_preflight_000002
```

or UUID-based IDs.

Requirements:

- unique for the current process;
- non-empty;
- <= 128 characters;
- no `/`;
- no backslash;
- no NUL.

Do not derive job IDs from file names or sensitive paths.

---

# 17. Health endpoint

Implement:

```text
GET /health
```

Suggested response:

```json
{
  "status": "ok",
  "service": "pixelscope-iqa-preflight",
  "iqa_implemented": false
}
```

Optionally include a simple application version such as `0.1.0`.

Do not include physical storage-root paths in `/health`.

---

# 18. Logging

Use ordinary Python logging.

Useful server-side information:

- job ID;
- lifecycle transition;
- number of scenes;
- logical `storage_root_id`;
- scene ID;
- variant ID;
- whether verification passed/failed;
- bounded exception category.

Avoid logging:

- image bytes;
- request body in full;
- full physical filesystem paths by default;
- secrets/credentials;
- unbounded tracebacks into API responses.

---

# 19. Error handling

Use normal HTTP errors for request/API problems discovered before job acceptance.

Examples:

- malformed JSON/model validation -> 400/422;
- unknown job -> 404;
- result unavailable -> 409.

For a valid accepted job, storage/environment verification errors should become terminal `failed` state with a bounded message.

The server process itself should remain alive after one job fails.

---

# 20. Required automated tests

Provide pytest coverage for at least the following.

## API/request tests

1. `/health` returns 200.
2. valid create request returns a non-terminal `queued` job.
3. variants other than exact ordered A/B are rejected.
4. zero scenes rejected.
5. more than 512 scenes rejected.
6. non-contiguous/wrong scene IDs rejected.
7. wrong source order rejected.
8. malformed SHA-256 rejected.
9. A/B metadata dimension mismatch rejected.
10. unknown status job returns 404.
11. result endpoint for an existing non-result job returns 409.

## Storage tests

12. valid contained relative path resolves under the configured root.
13. `../` traversal rejected.
14. absolute path rejected.
15. Windows drive path rejected.
16. backslash path rejected.
17. missing logical root produces verification failure.
18. missing file produces verification failure.
19. SHA mismatch produces verification failure.
20. image dimension mismatch produces verification failure.
21. valid image bytes + matching SHA + matching dimensions reach the intentional terminal state with message indicating:

```text
preflight source verification passed; IQA computation is not implemented
```

## Cancellation tests

22. configure a sufficiently long preflight hold.
23. create a valid job.
24. cancel before verification completes.
25. cancel response is `cancelled`.
26. later status remains `cancelled`.
27. background worker does not overwrite it with `failed`.

Tests should use temporary directories and generated tiny images. Do not require access to real corporate shared storage.

---

# 21. README requirements

The generated README must explain:

- this is a temporary preflight server, not an IQA implementation;
- supported Python version;
- how to create a virtual environment;
- how to install requirements;
- how to configure `PIXELSCOPE_STORAGE_ROOTS_JSON`;
- how to configure `PIXELSCOPE_PREFLIGHT_HOLD_SECONDS`;
- how to start Uvicorn listening on a chosen interface/port;
- firewall/network exposure is environment-specific and must follow internal policy;
- how to call `/health`;
- how to create a sample job with curl or PowerShell;
- how to poll status;
- how to cancel;
- how to run pytest;
- jobs are in-memory only and disappear on process restart;
- no IQA result is produced;
- a normal fully verified preflight job intentionally ends as `failed` with the IQA-not-implemented message.

Give Linux shell examples and, where quoting differs materially, PowerShell examples.

Do not hard-code any real internal hostname, mount path, share path, credential, or IP address.

Use placeholders such as:

```text
<SERVER_HOST>
<SERVER_PORT>
<SERVER_SHARED_ROOT>
```

---

# 22. Suggested manual acceptance sequence

The final answer should include a concise operator sequence equivalent to this.

## Step 1 — environment

```text
create venv
install requirements
set logical storage-root mapping
set preflight hold interval
start server
```

## Step 2 — health

```text
GET http://<SERVER_HOST>:<SERVER_PORT>/health
```

Expected conceptually:

```json
{
  "status": "ok",
  "service": "pixelscope-iqa-preflight",
  "iqa_implemented": false
}
```

## Step 3 — prepare real shared source

The engineer places or identifies A/B images that are visible both to the PixelScope Windows machine and the server through their respective mappings of the same logical root.

The request must contain the real SHA-256 and real dimensions.

## Step 4 — create

```text
POST /v1/iqa/jobs
```

Expected initial state:

```text
queued
```

## Step 5 — poll

```text
GET /v1/iqa/jobs/<job_id>
```

Expected progression:

```text
queued -> preparing -> failed
```

Expected final message when storage/source validation succeeded:

```text
preflight source verification passed; IQA computation is not implemented
```

This is the key proof that network + API + shared-storage source verification worked.

## Step 6 — cancel test

Increase the hold interval if necessary, create another job, then call:

```text
POST /v1/iqa/jobs/<job_id>/cancel
```

Expected stable terminal state:

```text
cancelled
```

---

# 23. Security boundary

This temporary implementation must not attempt to solve enterprise identity/authentication.

Specifically, do not add:

- SSO;
- OAuth;
- OIDC;
- SAML;
- bearer token requirement;
- credential persistence;
- custom certificate bypass;
- TLS verification disablement.

If the internal environment requires access restriction, deployment/network policy can restrict who can reach the temporary server without changing this API contract.

For real production deployment, HTTPS and corporate security requirements will be handled separately.

---

# 24. Explicit non-goals

Do not implement or simulate any of the following:

- IQA scoring;
- CNN/Transformer inference;
- GPU processing;
- feature extraction;
- weighted IQA aggregation;
- reference/target quality comparison;
- schema-v2 result generation;
- result manifest;
- NPZ artifacts;
- spatial grid result;
- historical result database;
- production scheduler;
- production persistence;
- production authorization;
- PixelScope desktop code.

The server stops at verified source accessibility.

---

# 25. Definition of done

The implementation is complete when all of the following are true:

1. server starts from documented commands;
2. `/health` responds;
3. exact valid PixelScope request can create a job;
4. create returns promptly as `queued`;
5. status polling works;
6. logical root + portable path is safely resolved;
7. server reads source bytes read-only;
8. SHA-256 is independently validated;
9. image dimensions are independently validated;
10. successful preflight deliberately terminates as `failed` with the exact semantic meaning that IQA is not implemented;
11. invalid storage/source data terminates with bounded diagnostic messages;
12. cancellation is observable and stable;
13. result endpoint does not fabricate a result;
14. automated tests cover protocol, storage containment, source verification, and cancellation;
15. README lets an engineer create the files and run the project without any other PixelScope documentation.

---

# 26. Required response format from you

Because you cannot modify files yourself, answer in this exact workflow.

### A. Short implementation summary

Explain the architecture in no more than a few paragraphs.

### B. Project tree

Show the complete file tree.

### C. Complete files

For every file, use this pattern:

```text
File: app/main.py
```

followed by one code block containing the **complete file contents**.

Do this for every file required to run the project.

Do not omit boilerplate by saying `same as above`, `etc.`, or `rest unchanged`.

### D. Installation commands

Give commands for creating the virtual environment and installing dependencies.

### E. Configuration commands

Show example environment variables using placeholders only.

### F. Server run command

Show the exact Uvicorn command.

### G. Manual API verification

Show `/health`, create, poll, result-unavailable, and cancel examples.

### H. Test command

Show the exact pytest command.

### I. Expected behavior

State clearly that a correctly verified normal preflight request ends as:

```text
failed
preflight source verification passed; IQA computation is not implemented
```

and that this is expected because the IQA algorithm is intentionally outside this project.

Do not claim that you executed or tested any command. The engineer will do that manually and report the results back to you.
