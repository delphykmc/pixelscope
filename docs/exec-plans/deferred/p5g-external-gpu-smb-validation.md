# Execution plan: P5-G — External GPU/SMB Validation & Closeout

Status: In progress — temporary external-server preflight observed; full GPU/result environment still unavailable
Owner: repository owner + P5-G implementation/review agents
Branch/PR: `validation/p5g-external-preflight` / PR #65
Last updated: 2026-08-28

## Goal

Validate the merged P5 client platform against the real production-shaped GPU API,
result writer, and mapped/shared storage. P5 is complete only when this plan records
observed external evidence and the final closeout is independently reviewed.

The currently available temporary external server is sufficient for transport,
job-lifecycle, and shared-source preflight validation, but it does not implement real IQA
computation or schema-v2 Result publication. A canonical terminal `failed` state after
successful source preflight is therefore expected evidence in this temporary environment,
not a COMPLETE/PARTIAL publication substitute.

## Scope

### In scope

- real external API and schema-v2 result-writer compatibility;
- Current Pair and deterministic Folder Pair end-to-end execution;
- COMPLETE/PARTIAL publication and early/late cancel/completion races;
- real shared-root mapping, staging, SMB access, and historical logical reopen/remap;
- Reference, Scene grid, native verification, spatial-load, and lifecycle observations;
- concurrent local Statistics/Difference/navigation while remote work is active;
- server build/algorithm identity and storage topology capture where available;
- measurement-backed, bounded corrections discovered by the real environment;
- final P5 closeout and activation of P6.

### Out of scope

- fabricating external PASS from localhost/mock probes;
- speculative cache, preload, adaptive polling, retry, WebSocket, or concurrency policy;
- authentication/SSO, credential lifecycle, permissions, audit, or administration;
- redesigning the frozen schema-v2 numerical/result or P5-C transport contracts.

## Inherited invariants

- `Registered → Selected → Current Comparison Page → Presented → Resident` remains the
  only local authority hierarchy and `Analysis Working Set = Current Comparison Page`.
- `ImageDocument.source` is native analytical authority; Display Gain is presentation
  only and Difference keeps its promoted-arithmetic semantics.
- P2 residency/cache/preload, P4 curation/session/history, Session v1, P5 schema-v2,
  P5-B canonical Results, P5-C jobs/storage, P5-D explicit Inspect, P5-E history, and
  P5-F bounded pool/transport lifetimes remain unchanged.
- External server measurements remain authoritative; PixelScope owns local
  reference-dependent comparison, reduction, and visualization.
- Remote IQA is an explicitly configured internal endpoint transport. Production
  `HttpIqaJobClient` explicitly bypasses process proxy routing (`HTTP_PROXY`,
  `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY`) by supplying an empty HTTPX proxy map.
  HTTPX environment trust remains enabled so HTTPS CA configuration such as
  `SSL_CERT_FILE` / `SSL_CERT_DIR` is not silently redefined by this proxy policy.
  Authentication/identity remain P6 concerns.

## Required observation matrix

| Area | Required observed evidence |
|---|---|
| API/result writer | frozen create/status/result/cancel paths and schema-v2 publication |
| Pairing | Current Pair and deterministic Folder Pair identity/order |
| Terminal states | COMPLETE, PARTIAL, failure, cancel, and completion race behavior |
| Shared storage | mapping, containment, staging, SMB permissions, and path portability |
| Historical flow | logical reopen, root remap, result-only mode, Provenance, Inspect/Return |
| Performance | manifest/summary/Reference/grid/source timings and bounded byte observations |
| Coexistence | local analysis/navigation responsiveness during remote work |
| Lifecycle | close/reopen, queued/running jobs, rapid Result/Scene intent changes |

Timing observations are characterization data, not correctness thresholds unless a
specific regression is deliberately frozen with evidence.

## Temporary external-server preflight boundary

Observed in the temporary external environment:

- external TCP/HTTP reachability;
- create/status transport and real job identity;
- serial polling to server-owned terminal state;
- cancellation lifecycle;
- logical-root/relative-path source identity;
- mapped-drive/canonical-path shared-root resolution on the client;
- server-side logical-root resolution and source verification;
- Jobs/UI Current Pair lifecycle integration;
- failed/cancelled Result non-publication;
- expected terminal `failed` after source verification because IQA computation is not
  implemented by the temporary server.

Not currently observable and never inferred from the temporary server:

- IQA/GPU computation;
- `succeeded`/`partial` publication;
- schema-v2 Result writer compatibility;
- COMPLETE/PARTIAL Result open/reference switching;
- Dataset/Scene reductions and spatial grid behavior;
- historical Result reopen/remap;
- full P5-G qualification.

### Remaining temporary-server closeout — Folder Pair multi-Scene

Current Pair already covers one-Scene production request preparation and external
lifecycle. Before moving exclusively to the real IQA server, one additional low-cost
observation is useful: submit a production-generated deterministic Folder Pair request
containing two or three Scenes and verify that the temporary server accepts the whole
multi-Scene source manifest, completes its source-preflight boundary, and then reaches
the same expected `failed` terminal because IQA computation is unavailable.

This is a **pending owner external observation**, not PASS evidence yet. The dedicated
`scripts/p5g_folder_pair_preflight.py` wrapper reuses the existing P5-G lifecycle
validator and adds pre-POST proof that the supplied request is:

- `submission_kind = folder_pair`;
- multi-Scene (`>= 2`);
- exact ordered A/B source shape for every Scene;
- the exact expected Scene count when `--expect-scene-count` is supplied.

The exact production request JSON already has a debug-only generation path; no second
request builder is introduced. With `PIXELSCOPE_REMOTE_IQA_DEBUG=1`, use IQA Setup to
validate the intended Folder Pair, then use its `Inspect JSON · DEBUG` action and copy
the generated request. Request JSON contains portable relative source identities and
hashes, so keep it as local validation material and do not commit it.

Example for a three-Scene temporary preflight:

```powershell
python -m scripts.p5g_folder_pair_preflight `
    $env:PIXELSCOPE_P5G_SERVER `
    .\p5g-folder-pair-request.json `
    --expect-scene-count 3 `
    --mode failed `
    --terminal-stability-requests 2
```

If the temporary server has a known non-sensitive terminal message token whose semantics
mean that its complete source-preflight phase passed, the existing optional
`--require-terminal-message-substring` check may also be used. Do not encode or publish
sensitive server text merely to satisfy this optional evidence.

Expected evidence is bounded to:

- request Scene count equals the locally expected count;
- request source count is two per Scene and A/B ordered;
- create returns a real non-terminal job identity;
- polling reaches the expected terminal `failed` and remains stable;
- failed Result remains unpublished;
- the server reaches its documented source-preflight-complete boundary before the
  expected not-implemented IQA failure.

This does **not** turn the temporary server into a COMPLETE/PARTIAL test environment and
does not justify fabricated schema-v2 Results.

Staging-root validation is not required merely to close this temporary-server pass. Run
it only if the intended deployment actually submits sources outside configured shared
roots and therefore depends on the P5-C staging path.

## Validation and review gate

1. Record the exact client head, server build/algorithm identity, storage topology,
   Windows/Python/Qt environment, and executed matrix.
2. Run focused tests for any bounded correction, then the full repository gates in
   `docs/QUALITY.md`.
3. Classify every result as PASS, regression, reproduced baseline failure, or
   environment-dependent validation debt. Unobserved items remain NOT OBSERVED or
   NOT VALIDATED.
4. Obtain independent latest-whole-head review.
5. Only after observed full external PASS, update ROADMAP/CURRENT_STATE/UI status, mark
   P5 Complete, archive this plan, and make P6 the active/next program.

## Progress log

- 2026-08-24: P5-F merged as PR #45 at
  `main@6634447fc3c48545a2482718dd3f444928806218`. No real GPU/SMB environment was
  available, so this gate was separated from the active repository refactoring program.
- 2026-08-27: owner observed real external temporary-server Current Pair create response,
  polling to expected terminal `failed`, and a cancellation path reaching `cancelled`.
  These are partial preflight observations only and do not validate IQA computation or
  schema-v2 Result publication.
- 2026-08-28: owner reproduced a corporate-proxy issue: DNS/TCP and explicit direct
  proxy routing reached the configured external server while environment-proxy routing
  timed out. PR #65 therefore gives Remote IQA an explicit no-proxy policy while keeping
  HTTPX environment trust enabled for HTTPS CA configuration.
- 2026-08-28: owner reproduced and corrected a mapped-drive canonical-path mismatch in
  shared-root resolution. With matching client/server logical root IDs, Current Pair UI
  submission reached the temporary server, server-side source verification passed, and
  the job then reached the expected `failed` terminal because IQA computation is not
  implemented. Focused and full repository validation were reported PASS before the
  independent latest-head review; affected gates must be rerun after review fixes.
- 2026-08-28: follow-up validation work prepared a dedicated Folder Pair multi-Scene
  preflight wrapper over the already merged P5-G lifecycle validator. External execution
  remains pending and no Folder Pair PASS is claimed by this repository change alone.

## Completion summary

Not complete. Temporary external transport/job/shared-source Current Pair preflight is
observed and a final Folder Pair multi-Scene temporary check is pending. No real GPU
computation, schema-v2 COMPLETE/PARTIAL Result publication, or full external GPU/SMB
qualification PASS is claimed.
