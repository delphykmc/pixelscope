# P5-G Temporary External IQA Server Handoff

Status: **Temporary integration-preflight contract; not production IQA**  
PixelScope source baseline: `main@70205acdb25099dbe807347df3f8906c62938156`  
Handoff branch: `handoff/p5g-temporary-server-contract`  
Audience: engineer / internal GPT building a short-lived server for PixelScope P5-G external connectivity and shared-storage validation

## 1. Purpose

The real GPU IQA service and schema-v2 result writer are still under development. PixelScope must not wait for the numerical IQA implementation before validating the parts of P5-G that can be observed independently in the real corporate network/server/storage environment.

Build a **small temporary external server** that implements the already-frozen PixelScope P5-C job transport contract closely enough to validate:

1. Windows PixelScope PC → external server DNS/routing/TCP/HTTP(S) connectivity;
2. the real `POST create → GET status` job protocol over the external network;
3. cancellation over the real network;
4. parsing of the exact current PixelScope request JSON;
5. server-side resolution of `storage_root_id + relative_path` into the server's mounted shared-storage path;
6. server read access to submitted image files;
7. SHA-256 and image-dimension agreement between PixelScope request metadata and the bytes visible to the server.

This project is deliberately **not** an IQA implementation. A successful preflight job should normally end in the canonical terminal `failed` state with a bounded message explaining that IQA computation is not implemented. It must not fabricate `succeeded`, `partial`, schema-v2 measurements, or a result artifact merely to make PixelScope appear to pass.

The evidence produced by this temporary server is **P5-G preflight evidence only**. It must not be recorded as overall P5-G PASS or P5 completion.

## 2. Authoritative PixelScope sources

Do not infer the current API from the historical `server/api_contract.md`; that file is explicitly unsupported history.

Use these files as authority, in this order:

- `docs/REMOTE_IQA_CONTRACT.md`
  - durable product/transport/storage ownership;
  - current `/v1/iqa/jobs` endpoint family;
  - job states and result-reference rules;
  - logical shared-storage contract.
- `src/pixelscope/remote/iqa_submission.py`
  - exact request JSON produced by the current client;
  - ordered variants A/B;
  - 1..512 Scene limits;
  - deterministic Scene IDs;
  - source locator/hash/dimension fields.
- `src/pixelscope/remote/iqa_client.py`
  - exact response fields accepted by `HttpIqaJobClient`;
  - status/protocol validation;
  - HTTP/TLS behavior.
- `src/pixelscope/remote/iqa_storage.py`
  - portable POSIX `relative_path` rules;
  - client-side logical-root semantics.
- `src/pixelscope/remote/iqa_compatibility_probe.py`
  - bounded create/status/result/cancel probe semantics.
- `scripts/p5f_iqa_probe.py`
  - owner-facing live-server probe command.
- `docs/REMOTE_IQA_INTEGRATION_CHARACTERIZATION.md`
  - P5-F evidence boundary and P5-G live-server characterization plan.
- `docs/exec-plans/deferred/p5g-external-gpu-smb-validation.md`
  - final P5-G observation matrix and the rule that mock/localhost evidence is not external PASS.

The existing `src/pixelscope/remote/iqa_localhost_server.py` may be read as a **debug/fault-harness example only**. Do not treat its internal design as the required production server architecture.

## 3. Scope boundary

### Required now

The temporary server must provide:

- one externally reachable server process;
- the canonical P5-C job endpoints;
- exact request-shape validation for the current two-variant client contract;
- durable-enough in-process job state for polling during one test session;
- server-side logical shared-root configuration;
- contained path resolution;
- read-only source verification;
- deterministic `queued → preparing → failed` behavior after successful preflight;
- a real cancellation path that can end a non-terminal job as `cancelled`;
- bounded logs/diagnostics sufficient to correlate a PixelScope job with server observations.

### Explicitly not required now

Do **not** implement or fake:

- IQA algorithms, GPU inference, feature extraction, or numerical measurement;
- schema-v2 `manifest.json`, `summary.npz`, Scene grid NPZs, or detail artifacts;
- `succeeded` or `partial` jobs;
- a fake Result reference;
- Reference switching, Dataset/Scene reductions, spatial IQA grids, or Viewer inspection results;
- historical Result persistence/reopen;
- production database/queue/scheduler architecture;
- P6 SSO, OAuth/OIDC/SAML, token storage, token refresh, permissions, or audit policy;
- automatic retries beyond the existing client behavior;
- WebSocket transport;
- a new PixelScope request field just for this temporary server.

Authentication/SSO is a P6 concern. Do not invent an auth header or login flow for this temporary project. If corporate policy requires access restriction, use an approved environment/network control or other explicitly approved test mechanism without changing the PixelScope P5-C API contract.

## 4. Target topology

Conceptually:

```text
PixelScope on Windows
    │
    │  HTTP(S), canonical /v1/iqa/jobs API
    ▼
Temporary external IQA preflight server
    │
    │  storage_root_id + relative_path
    ▼
Server-side configured shared root
    │
    ▼
Mounted/shared image bytes
```

Client and server physical paths are intentionally different.

Example only:

```text
portable identity
    storage_root_id = iqadata
    relative_path   = project42/A/0001.png

Windows client mapping
    iqadata -> <CLIENT_SHARED_ROOT>

server mapping
    iqadata -> <SERVER_SHARED_ROOT>
```

`<CLIENT_SHARED_ROOT>`, `<SERVER_SHARED_ROOT>`, hostnames, ports, credentials, and real corporate paths are deployment-specific values. **Do not commit real internal secrets or sensitive paths to this handoff branch.**

## 5. Canonical HTTP endpoints

Implement this endpoint family exactly:

```text
POST /v1/iqa/jobs
GET  /v1/iqa/jobs/{job_id}
GET  /v1/iqa/jobs/{job_id}/result
POST /v1/iqa/jobs/{job_id}/cancel
```

An optional operational endpoint such as:

```text
GET /health
```

is useful for curl/browser/process monitoring, but it is **not part of the PixelScope P5-C product contract** and PixelScope does not depend on it.

Use JSON objects for canonical endpoint responses. Normal successful API responses should use an HTTP 2xx status.

`HttpIqaJobClient` accepts `http` and `https`. TLS verification is always enabled for HTTPS. Do not disable certificate verification in PixelScope. Prefer a corporate-approved HTTPS endpoint when available. If an approved internal HTTP endpoint is used temporarily, record that only as transport/connectivity preflight; it is not production TLS qualification.

## 6. Exact create-job request shape

PixelScope serializes the current P5-C request as:

```json
{
  "submission_kind": "<opaque-current-client-value>",
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
          "sha256": "<64-lowercase-hex-sha256>",
          "width": 1920,
          "height": 1080
        },
        {
          "variant_id": "B",
          "storage_root_id": "iqadata",
          "relative_path": "project42/B/image_0001.png",
          "sha256": "<64-lowercase-hex-sha256>",
          "width": 1920,
          "height": 1080
        }
      ]
    }
  ]
}
```

Important details:

- the current initial client submission contract is exactly two ordered variants: `A`, then `B`;
- `variants` is an array of objects, not an array of strings;
- every Scene contains exactly one A source followed by exactly one B source;
- Scene IDs are deterministic and contiguous:
  - `scene_000000`
  - `scene_000001`
  - ...
- valid request size is 1..512 Scenes;
- source fields are exactly the portable locator/identity data shown above;
- **there is no `source_id` in the current P5-C request**;
- current remote-eligible source formats are PNG, JPG/JPEG, and BMP;
- PixelScope client preflight already requires A/B dimensions to match inside each Scene, but the server should independently reject/terminal-fail inconsistent or corrupt external input rather than trusting the client blindly;
- `submission_kind` should be accepted as the current client-provided non-empty identity. The temporary server does not need to invent new behavior based on it.

Do not add temporary control fields such as `test_mode`, `force_failure`, or `delay_seconds` to this request. If the temporary server needs test timing/mode controls, configure those on the **server process/environment**, not in the frozen PixelScope request schema.

## 7. Create-job response

For a structurally valid request that the server accepts for preflight work, return a real unique job ID and a **non-terminal** state.

Recommended response:

```json
{
  "job_id": "job_preflight_000001",
  "state": "queued"
}
```

Client constraints that matter:

- `job_id` must be non-empty;
- keep it at most 128 characters;
- do not include `/`, `\\`, or NUL;
- create response must not report a terminal state;
- if `state` is omitted PixelScope defaults it to `queued`, but explicitly returning `queued` is clearer.

The create POST is intentionally non-idempotent from the client's perspective and is **never blindly retried** after an ambiguous timeout/connection/5xx outcome. Therefore the temporary server should return the accepted `job_id` promptly and perform storage verification asynchronously or after the create response rather than blocking the create request for a long time.

Malformed JSON, malformed request structure, unsupported cardinality/order, or clearly invalid protocol data may be rejected with a normal 4xx response before a job is created.

Environment/data problems discovered after accepting a valid request should normally become a terminal job status rather than creating a second ad-hoc API.

## 8. Job states and temporary state machine

PixelScope recognizes exactly these states:

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

Terminal states:

```text
succeeded
partial
failed
cancelled
```

For this temporary server, use only states that reflect real work. Because no IQA exists yet, the preferred normal preflight lifecycle is:

```text
POST create
    ↓
queued
    ↓
preparing
    ↓
verify logical roots / source bytes / SHA / dimensions
    ↓
failed
    message = "temporary preflight server: IQA computation is not implemented"
```

Do **not** transition through `extracting`, `aggregating`, or `writing` merely to simulate production progress.

Do **not** finish as `succeeded` or `partial` unless a real schema-v2 result writer later exists and the corresponding result is actually published.

Once a job reaches a terminal state, subsequent status reads should remain stable for that job during the lifetime of the test server.

For this temporary project, in-memory job storage is acceptable. A server restart may lose jobs, provided this is clearly documented as a temporary limitation. Production durability is not being designed here.

## 9. Status response

Canonical endpoint:

```text
GET /v1/iqa/jobs/{job_id}
```

Return:

```json
{
  "job_id": "job_preflight_000001",
  "state": "preparing",
  "completed_scenes": 0,
  "total_scenes": 1,
  "message": "validating shared-storage sources"
}
```

or terminal preflight completion:

```json
{
  "job_id": "job_preflight_000001",
  "state": "failed",
  "completed_scenes": 0,
  "total_scenes": 1,
  "message": "temporary preflight server: IQA computation is not implemented"
}
```

Response rules enforced by PixelScope:

- returned `job_id` must exactly match the requested ID;
- `state` must be one of the canonical values above;
- `completed_scenes` and `total_scenes`, when supplied, must be non-negative integers;
- `completed_scenes <= total_scenes`;
- `message` is optional and should be a short human-readable string;
- do not return secrets, physical local paths, stack traces, or unbounded exception text in `message`.

For storage validation failure, a bounded example is:

```json
{
  "job_id": "job_preflight_000001",
  "state": "failed",
  "completed_scenes": 0,
  "total_scenes": 1,
  "message": "source verification failed: unknown storage root"
}
```

The server may retain more detailed diagnostics internally, but PixelScope status messages should remain bounded and non-sensitive.

## 10. Cancel behavior

Canonical endpoint:

```text
POST /v1/iqa/jobs/{job_id}/cancel
```

The temporary server must make cancellation observable while a job is still `queued` or `preparing`.

A simple deterministic mechanism is to configure a server-side preflight hold/delay so an operator can run a cancel probe before the job reaches its deliberate `failed` terminal state. The delay belongs to server configuration, not the PixelScope request JSON.

A direct terminal cancel response is acceptable:

```json
{
  "job_id": "job_preflight_000001",
  "state": "cancelled",
  "completed_scenes": 0,
  "total_scenes": 1,
  "message": "cancelled"
}
```

The returned job ID must match. After cancellation, subsequent status reads should report `cancelled` consistently.

The durable P5 contract allows server-owned cancellation semantics; the temporary server does not need to design GPU-kernel cancellation. It only needs a truthful queued/preparing cancellation path.

## 11. Result endpoint behavior while IQA is unavailable

The endpoint path should exist:

```text
GET /v1/iqa/jobs/{job_id}/result
```

However, normal PixelScope/probe behavior calls it only after `succeeded` or `partial` has been observed.

Because this temporary server must not emit those states, **normal preflight runs will not call the Result endpoint**.

If it is called for a job with no published result, return a clear non-2xx response such as HTTP 409 with a small JSON error object, for example:

```json
{
  "detail": "result is not published"
}
```

This mirrors the repository's existing debug server behavior and, more importantly, avoids fabricating a result reference.

When the real server later implements a published Result, the canonical successful Result reference must have:

```json
{
  "job_id": "<same-job-id>",
  "storage_root_id": "<logical-root-id>",
  "relative_path": "<portable-result-relative-path>",
  "schema_version": 2,
  "publication_state": "complete"
}
```

or `publication_state = "partial"` for a real `partial` terminal job. That future result-writer work is **not part of this temporary project**.

## 12. Shared-storage contract

The API never uses a Windows mapped drive or a Linux mount path as portable identity.

The server needs deployment configuration conceptually equivalent to:

```text
storage root mapping
    "iqadata" -> <SERVER_MOUNT_PATH_FOR_IQADATA>
    "another_root" -> <SERVER_MOUNT_PATH_FOR_ANOTHER_ROOT>
```

The exact config format is implementation-specific (environment variable, JSON/YAML config, CLI option, etc.). Keep configuration outside request identity.

For every submitted source:

1. read `storage_root_id`;
2. find the corresponding configured **server-local** root;
3. validate `relative_path` as a contained portable POSIX path;
4. join/resolve it under that root without allowing escape;
5. ensure the resolved target is a readable regular file;
6. read the file without modifying it;
7. compute SHA-256 in a streaming/bounded-memory manner;
8. compare it to the request `sha256`;
9. read image dimensions and compare them to request `width` / `height`;
10. record only bounded verification status for the job.

PixelScope's portable path rules reject:

- empty paths;
- NUL;
- absolute POSIX paths;
- Windows absolute/drive paths;
- `.` or `..` path components;
- backslash-based paths.

The server must enforce equivalent containment independently. Do not trust a relative-looking string and concatenate it without containment checking.

Where feasible, reject a symlink/junction/path-resolution escape from the configured root. At minimum, the final resolved file must remain under the configured root before opening it.

The temporary server has **read-only** responsibility for input sources. It must not rename, delete, overwrite, normalize, transcode, resize, or otherwise mutate PixelScope-submitted files.

## 13. Source verification and image formats

The current client submits only:

```text
.png
.jpg
.jpeg
.bmp
```

For each source, verify at least:

```text
file exists/readable
SHA-256 matches request
width matches request
height matches request
```

A standard image decoder/library may be used for dimension verification. The temporary server does not need to perform color conversion or decode the full image into GPU tensors merely for this preflight.

For a Scene, also verify that the two submitted sources have equal requested/observed dimensions. A real PixelScope client should already have enforced this, so a mismatch is useful evidence of transport/storage corruption or a noncanonical request.

A successful source/storage verification still ends in deliberate `failed` because IQA is absent. The distinction should be visible in the server logs and/or bounded status message:

```text
transport accepted           PASS
request schema               PASS
storage root resolution      PASS
source byte verification     PASS
image dimension verification PASS
IQA computation              NOT IMPLEMENTED
job terminal state           failed (intentional preflight terminal)
```

## 14. Request validation expectations

The temporary server should reject clearly malformed create requests rather than silently repairing them.

At minimum validate:

- JSON root is an object;
- `submission_kind` is present and non-empty;
- `variants` is exactly ordered A/B for the current initial client contract;
- `scenes` is an array with 1..512 entries;
- Scene IDs are exactly `scene_000000 ... scene_<N-1>` in order;
- each Scene has exactly two sources in ordered A/B variant order;
- every source has non-empty `storage_root_id` and portable `relative_path`;
- every source has a canonical SHA-256 string;
- `width` and `height` are positive integers.

Do not resize, reorder, renumber, invent missing variants, or synthesize a Scene to make malformed input succeed.

The HTTP body-size safety limit is implementation-specific, but it must be high enough to accept a valid current-client request at the supported maximum of 512 Scenes. The repository's localhost fault harness uses an 8 MiB cap as a debug safeguard; this is not a new production limit contract.

## 15. Concurrency and lifecycle requirements

A heavyweight production scheduler is unnecessary. The temporary server only needs safe behavior for a few concurrent test jobs/polls.

Minimum expectations:

- create returns promptly;
- storage verification does not block all status/cancel handling;
- per-job state updates are thread-safe/consistent;
- a job has one stable ID;
- status reads do not advance the job by accidentally creating duplicate work;
- cancel does not create another job;
- terminal state is stable;
- server shutdown is clean enough for repeated test sessions.

It is acceptable to use an in-memory map guarded by the framework/runtime's normal synchronization primitives.

Do not introduce automatic duplicate create retries on the server/client boundary as a workaround for failed tests. PixelScope intentionally treats ambiguous CREATE outcome as special.

## 16. Network / deployment requirements

The process must be reachable from the actual PixelScope Windows validation PC, not only from `127.0.0.1` on the server.

Before PixelScope integration, establish and record:

- server host identity used by the test environment;
- listening port;
- whether transport is HTTP or HTTPS;
- whether the Windows PC can resolve/reach the host;
- firewall/network rule approval as applicable;
- server process start/restart procedure;
- shared-root IDs configured on the server;
- server process read access to the mounted roots.

Do not put actual credentials, tokens, secret URLs, private certificates, or protected path values in this public/source handoff document. Keep those values in the authorized internal deployment environment.

## 17. Logging and diagnostics

Logging exists to correlate external evidence, not to create a new product telemetry system.

Recommended bounded fields:

```text
timestamp
server build/commit identity
job_id
operation/endpoint
state transition
scene count
storage_root_id
source verification PASS/FAIL counts
cancel observed yes/no
bounded failure category
operation duration
```

Avoid logging:

- image bytes/content;
- bearer/session tokens;
- browser cookies;
- authorization headers;
- full request bodies in normal operation;
- unrestricted exception traces into client-visible messages;
- unnecessary client-local physical paths.

If request capture is temporarily useful for server debugging, make it an explicit internal debug option and protect it according to corporate policy. It is not part of the PixelScope contract.

## 18. Optional health endpoint

An optional endpoint is useful before testing the job protocol:

```text
GET /health
```

Example:

```json
{
  "status": "ok",
  "service": "pixelscope-iqa-preflight",
  "iqa_available": false
}
```

This must not be mistaken for P5 job compatibility. `/health` PASS proves only that an HTTP process is reachable.

## 19. Required acceptance scenarios for the temporary server

### Scenario A — external connectivity

From the PixelScope Windows PC:

- server hostname resolves/reaches;
- TCP/HTTP(S) request succeeds;
- optional `/health` returns expected response.

Evidence label:

```text
External connectivity: PASS
```

Not:

```text
P5-G: PASS
```

### Scenario B — real create/status/source preflight

Use a real PixelScope-shaped request whose files are visible through the shared-root mapping.

Expected flow:

```text
POST /v1/iqa/jobs -> queued + real job_id
GET status        -> queued/preparing
server verifies all source locators/hashes/dimensions
GET status        -> failed
message           -> IQA not implemented
```

Required observed server evidence:

- exact Scene count accepted;
- ordered A/B sources accepted;
- every logical root resolved;
- every source readable;
- every SHA-256 matched;
- every dimension matched;
- deliberate terminal failure occurred only because IQA is unavailable.

### Scenario C — cancellation

Configure enough server-side preflight delay to cancel while non-terminal.

Run create/status/cancel and observe:

```text
queued/preparing -> cancel -> cancelled
```

Subsequent status must remain `cancelled`.

### Scenario D — storage error classification

Temporarily use a controlled bad mapping or unavailable test source and confirm that the server does **not** crash or fabricate a result. The accepted job should reach `failed` with a bounded non-sensitive storage/source verification message.

Do not use protected production data merely to force an error scenario.

## 20. PixelScope-side probe after the server is ready

PixelScope already contains a bounded compatibility probe. Do not create another client protocol solely for this temporary server.

Command:

```powershell
.\.venv\Scripts\python.exe scripts\p5f_iqa_probe.py `
    <server-base-url> <request.json>
```

The request file must follow the exact shape in Section 6. Prefer a request generated from the real current PixelScope request-building path rather than a permanently hand-maintained parallel schema.

For cancellation:

```powershell
.\.venv\Scripts\python.exe scripts\p5f_iqa_probe.py `
    <server-base-url> <request.json> `
    --cancel-after-status-requests 1
```

The probe intentionally records bounded protocol metadata and excludes the server URL, request body, credentials, source content, and detailed transport exception text.

A normal temporary-server run ending in canonical `failed` is a valid **transport/job-lifecycle preflight observation** when the server evidence proves storage/source checks passed. It is not a numerical/result PASS.

After command-level probes, exercise the PixelScope IQA Jobs UI against the same server to verify the user-visible create/poll/failed/cancel behavior over the real environment.

## 21. Evidence that PixelScope should record from this temporary server

When the temporary server is deployed, P5-G preflight should record:

```text
PixelScope client exact commit
Temporary server exact project commit/build identity
Test date/time
Windows environment
Server environment/runtime
Transport scheme
Server host/port identity (in the authorized internal evidence location)
Configured logical storage_root_id values
Shared-storage topology description
Request type: Current Pair or Folder Pair
Scene count
Create/status/cancel observations
Source verification counts
Operation timings as observations only
Any environment failure
```

Do not convert observed timings into correctness thresholds yet.

Recommended status matrix after this temporary-server phase:

```text
External network connectivity      OBSERVABLE NOW
Canonical REST create/status       OBSERVABLE NOW
Cancel lifecycle                   OBSERVABLE NOW
Logical shared-root mapping        OBSERVABLE NOW
Server source read                 OBSERVABLE NOW
SHA-256 identity                   OBSERVABLE NOW
Source dimensions                  OBSERVABLE NOW
IQA measurement                    NOT AVAILABLE
extracting/aggregating/writing     NOT VALIDATED
COMPLETE/PARTIAL publication       NOT VALIDATED
schema-v2 Result writer            NOT VALIDATED
Result open/Reference/grid         NOT VALIDATED
Historical result reopen           NOT VALIDATED
P5-G overall                       NOT COMPLETE
```

## 22. What the internal GPT implementation should deliver

The internal implementation project should be small and disposable, but reproducible.

Please deliver at least:

1. a standalone temporary server project/repository or clearly isolated internal project directory;
2. README with environment setup and one launch command;
3. dependency file/lock mechanism appropriate to the internal environment;
4. server configuration for logical storage-root mapping without committed secrets;
5. canonical four P5-C endpoints;
6. optional `/health` endpoint clearly labeled non-contract;
7. in-memory job lifecycle implementation;
8. read-only shared-storage source verification;
9. configurable preflight delay/hold to make cancel testing deterministic;
10. focused tests for:
    - exact request acceptance;
    - malformed request rejection;
    - A/B and Scene ordering;
    - unknown/escaping relative paths;
    - SHA mismatch;
    - dimension mismatch;
    - normal deliberate-failed lifecycle;
    - cancellation;
    - unknown job;
    - result-not-published behavior;
11. a way to report the server git commit/build identity for P5-G evidence;
12. no IQA/result fabrication.

Framework choice is not part of the PixelScope contract. Use a simple internal-approved Python HTTP framework/runtime that can expose these semantics clearly. Do not spend time reproducing the full production GPU architecture.

## 23. Completion criterion for this temporary project

The temporary server is ready for handoff when all of the following are true:

- it runs on the intended external test server;
- PixelScope's Windows validation PC can reach it;
- it accepts the exact current P5-C request JSON;
- it returns a real non-terminal create response;
- status polling works;
- logical-root + relative-path resolution reaches the intended shared files;
- SHA-256 and dimensions are verified server-side;
- the successful preflight path deliberately ends `failed` only because IQA is not implemented;
- cancellation can produce stable `cancelled`;
- no fake schema-v2 result is published;
- the exact temporary-server commit/build identity can be recorded.

At that point, PixelScope can begin P5-G external **preflight** validation while the real IQA computation/result-writer work continues separately.

## 24. Future replacement by the real IQA server

The temporary server is intentionally disposable. The real GPU IQA server should later replace it behind the same frozen P5-C transport/storage boundary.

The intended progression is:

```text
Temporary external preflight server
    ↓
P5-G connectivity / REST / storage evidence
    ↓
real GPU IQA + schema-v2 result writer becomes available
    ↓
1-Scene COMPLETE end-to-end validation
    ↓
Folder Pair / PARTIAL / cancellation race / historical reopen / performance matrix
    ↓
P5-G external PASS
    ↓
P5 Complete
```

Do not change PixelScope's frozen request/job/storage contract merely because the temporary implementation is easier with another shape. If an actual incompatibility is found, report the concrete mismatch back to the PixelScope P5-G owner and reconcile it deliberately against `docs/REMOTE_IQA_CONTRACT.md` rather than silently creating a forked server contract.
