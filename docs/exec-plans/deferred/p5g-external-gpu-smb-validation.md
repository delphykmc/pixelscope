# Execution plan: P5-G — External GPU/SMB Validation & Closeout

Status: Deferred — waiting for a realistic external GPU server and SMB/shared-storage environment
Owner: repository owner + future P5-G implementation/review agents
Branch/PR: not started
Last updated: 2026-08-24

## Goal

Validate the merged P5 client platform against the real production-shaped GPU API,
result writer, and mapped/shared storage. P5 is complete only when this plan records
observed external evidence and the final closeout is independently reviewed.

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

## Validation and review gate

1. Record the exact client head, server build/algorithm identity, storage topology,
   Windows/Python/Qt environment, and executed matrix.
2. Run focused tests for any bounded correction, then the full repository gates in
   `docs/QUALITY.md`.
3. Classify every result as PASS, regression, reproduced baseline failure, or
   environment-dependent validation debt.
4. Obtain independent latest-whole-head review.
5. Only after observed external PASS, update ROADMAP/CURRENT_STATE/UI status, mark P5
   Complete, archive this plan, and make P6 the active/next program.

## Progress log

- 2026-08-24: P5-F merged as PR #45 at
  `main@6634447fc3c48545a2482718dd3f444928806218`. No real GPU/SMB environment was
  available, so this gate was separated from the active repository refactoring program.

## Completion summary

Not complete. No external GPU/SMB PASS is claimed.
