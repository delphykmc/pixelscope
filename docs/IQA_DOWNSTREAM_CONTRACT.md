# IQA downstream consumer and transfer contract

Status: **Slice 5 reconciled contract**. The downstream semantic/transfer contract is
reviewable and mergeable; actual SUB transfer qualification remains gated by Slice 4 /
Checkpoint C and Slice 6 production evidence.
Reconciled MAIN baseline: `main@bc4090e8e6594089ee47b6dd181700d7ce301482`
(merged Slice 2 / PR #125).
Last updated: 2026-10-05.

## Authority and scope

Read [Issue #121](https://github.com/delphykmc/pixelscope/issues/121), its
[confirmed Checkpoint A](https://github.com/delphykmc/pixelscope/issues/121#issuecomment-5993880778),
merged [Slice 0 / PR #122](https://github.com/delphykmc/pixelscope/pull/122),
merged [Slice 1 / PR #123](https://github.com/delphykmc/pixelscope/pull/123),
merged [Slice 2 / PR #125](https://github.com/delphykmc/pixelscope/pull/125),
[IQA ownership](IQA_OWNERSHIP.md), and
[boundary characterization](IQA_BOUNDARY_CHARACTERIZATION.md) as the authority.
Checkpoint A confirms the intended enterprise workflow; characterization freezes
existing behavior and lifetime constraints rather than the historical transport API.

Slice 2 establishes the Client-owned Qt-free public seam in
`remote/iqa_public_contract.py`: `IqaExecutionPort` for execution/control and
`IqaResultAccessPort` for materialization/result/source access, with normalized
`IqaResult` data and lazy `IqaSpatialAccess`. `remote/iqa_public_adapter.py` is a
transitional MAIN adapter proving the existing P5 behavior can satisfy that seam; it is
not an Enterprise implementation or a new ownership direction.

SUB must supply Enterprise IQA through these Client-owned semantics without changing
MAIN-owned Base or IQA Client source. MAIN remains runnable with public/synthetic data.
The remaining injection/composition site belongs to Slice 4. References here to
execution, artifact access, resolver, transfer and cleanup describe downstream
responsibilities and do not authorize parallel public protocols.

This contract delivers downstream design, transfer policy, and validation plans only.
Confidential implementation, schema conversion code, settings migration, package moves,
SSO implementation, packaging runs, and production integration are out of scope.

## Responsibility boundary

| Concern | Owner and observable obligation |
|---|---|
| Generic host | Base hosts menus/docks/settings, selection/viewer access, workers and lifecycle primitives. It does not own IQA semantics. |
| IQA Client | MAIN owns IQA actions/dock, submission intent, job/result presentation, normalized result/domain, history, reference/scene selection, lazy grid requests, generation/stale-result rejection. |
| Execution/control | SUB authenticates, submits, tracks queue/execution, adapts completion/failure, and implements optional backend cancellation through `IqaExecutionPort`. |
| Artifact/data | SUB stages local inputs, accesses published artifacts, transfers and normalizes results, resolves sources, and manages remote retention/cleanup through `IqaResultAccessPort` semantics. |
| Composition | SUB's explicit launcher will supply Enterprise implementations through the merged public seams once Slice 4 provides the approved injection point. Client/Base retain their existing resource ownership. No runtime discovery framework is required. |
| Enterprise configuration | SUB owns endpoint defaults/overrides, storage topology, auth/security, backend schemas, deployment and internal evidence. |

Dependencies remain `Enterprise IQA -> IQA Client -> Base`. Providers supply plain
data/non-UI operations and do not create QWidget/QObject/QThreadPool objects merely
to provide IQA. Client scheduling stays off the UI thread using existing resource
domains. A provider owns its non-Qt backend resources and deterministic release;
release must be idempotent and must not rely on cyclic GC or retain a UI owner.
Existing startup/install order, pool identities/cardinality, and close semantics in
the characterization remain protected. Missing injection capability is an upstream
gap, not permission to patch a window/controller downstream.

### Provider call concurrency — reconciled with Slice 2

The merged public ports explicitly permit **same-instance overlapping Client-worker
calls**. `IqaExecutionPort` implementations must be safe for concurrent calls by being
thread-safe/reentrant or by internally serializing their backend; the Client does not
promise per-instance serialization. `IqaResultAccessPort` has the same requirement for
overlapping `materialize`, `open_result`, and `resolve_source` work, and
`IqaSpatialAccess` requires concurrent-safe lazy scene access.

The transitional `P5IqaExecutionAdapter` demonstrates the allowed internal-
serialization model using an `RLock`, while the public contract remains independent of
that implementation. SUB therefore owns concurrency safety for any shared non-Qt
transport/session/cache/transfer resources behind a provider instance. Conformance must
exercise overlap and cancellation/release races rather than only serial calls. Preserve
existing pool ownership/cardinality and off-thread work; no new pool, UI-thread
serialization, or lifecycle redesign is implied.

## Control plane flow

1. Client captures `IqaSubmissionIntent` from the underlying current pair or supported
   folder/path workflow. Existing eligibility, pair ordering, source identity and bounds
   remain unchanged. Presentation state is not request authority.
2. Enterprise validates configuration/access and stages the inputs before remote
   acceptance. It translates the public intent to its private request representation.
3. Submission yields stable `IqaJobReference`; successful publication yields opaque
   `IqaResultReference`. Backend identifiers, endpoint and storage topology remain
   private implementation data. Never blindly retry a possibly accepted create:
   `IqaProviderErrorKind.AMBIGUOUS_SUBMIT` is the public uncertainty contract.
4. Adapt queued/running/terminal behavior into `IqaJobState`, `IqaJobProgress` and
   `IqaJobSnapshot`. `IqaExecutionCapabilities.can_cancel` exposes optional cancellation.
   Provider failures cross the boundary only as sanitized `IqaProviderError`; raw
   provider exception text, endpoint, credential or proprietary payload detail must not
   enter Client-facing messages.
5. Socket notifications, polling, HTTP and reconnection are Enterprise details. A
   duplicate, delayed or reordered notification cannot regress a terminal state,
   attach another job's result, or publish into a revoked Client generation. The
   Enterprise implementation reconciles notification claims with its own authority.
6. Remote execution completion and result materialization are intentionally separate
   responsibilities. Artifact acquisition failures stay recoverable without resubmit
   and without rewriting the terminal execution outcome. Failed/cancelled work must not
   fabricate an openable result. Completion never automatically opens Results.

Client close revokes UI publication and cancels pending Client work; it does not imply
remote cancellation of a durable job. Enterprise must honor cooperative abort before
remote acceptance, release backend resources on shutdown, and leave server-owned jobs
and required inputs intact. Cancellation of local waiting/transfer is distinct from
cancelling server execution and from deleting remote artifacts.

## Data plane and cleanup flow

```text
Client intent + selected local sources
  -> Enterprise preflight / verified shared staging
  -> private execution submit / queue / completion
  -> Enterprise published artifact acquisition
  -> private-response to public-domain normalization
  -> verified local result publication
  -> explicit Client Open Result / later standalone reopen
  -> Enterprise remote cleanup when retention permits
```

SUB maps local input identities to shared staging accessible to the GPU server.
Client/server physical paths need not match. Copy/hash/staging work is off-thread;
physical shared paths and private root mappings do not enter the public port.
Preserve encoded source identity, dimensions, dtype/channel/geometry semantics and
deterministic request ordering. Do not silently resize, realign or reinterpret images.
Verify content and resolved containment before reuse/publication. Concurrent users
must have isolated ownership of mutable staging, temporary files and cleanup records;
shared content reuse does not give a user deletion authority over another job's input.

Result acquisition uses the identity returned for this job, not a directory scan for
the latest result. SUB validates publication/completeness and protects bounded reads,
path containment, integrity and concurrent download behavior. Transfer retries are
bounded and apply only to safely repeatable operations; authentication failure,
corruption and ambiguous submit are not generic retry triggers. A retry must retain
the expected job/result identity and cannot open partially downloaded files.

Remote cleanup is Enterprise policy, never a public Client path-deletion command.
SUB tracks which resources it owns, which durable jobs still reference them, and
whether a verified local publication exists. Delay deletion of result artifacts until
required local artifacts are durable; delay input deletion until execution and the
retention policy permit it. Failed/aborted transfers remain recoverable. Cleanup
failure must preserve the local result and expose a bounded maintenance outcome
inside SUB. Make cleanup repeatable, scoped and safe under concurrency; application
close is not authority to recursively delete staging or published results. SUB owns
orphan/expired-resource recovery when no Client session is active.

## Normalization and durable local materialization

Enterprise adapts proprietary responses into the **same Client-owned `IqaResult`
domain** used by MAIN synthetic fixtures. Preserve stable result identity, dataset
metadata, ordered scenes/variants/attributes, labels, scalar/per-scene values, value
kind/direction/range, measurement context, source bindings, completeness and sanitized
diagnostics. Private schema fields, credentials, internal endpoints and raw payloads
stay in SUB.

Slice 2 provides explicit public availability/completeness semantics:
`IqaAvailability`, `IqaResultCompleteness`, `IqaMeasurementSummary`,
`IqaSpatialLoadOutcome`, and `IqaDiagnostic`. This is sufficient for Client-side
representation of available/partial/missing/failed data. It does **not** by itself
choose a durable on-disk encoding for every possible missing metric.

The current [schema-v2 contract](REMOTE_IQA_V2_SPEC.md) requires fully shaped
successful scenes; PARTIAL records every requested scene outcome and excludes
failed/cancelled scenes from numerical summaries. It is not a general arbitrary
missing-metric serialization. If Enterprise data contains a metric-level absence that
cannot be faithfully encoded in the Client-supported durable format, treat it as the
remaining G4 encoding decision below; do not replace it with zero, relax successful-
scene invariants, or invent downstream-only numerical semantics.

The existing `remote/iqa_result_reader.py` remains the canonical versioned local
loader, while Slice 2 proves `IqaExplorerModel` can consume a normalized `IqaResult`
without changing existing numerical meaning. Durable serialization must remain a
Client-readable supported format, with schema-v1 kept read-only. No parallel Enterprise
numerical engine is introduced into Client code.

Materialization must satisfy this transaction:

1. Acquire/normalize into an isolated temporary local destination. Preserve expected
   identity and validate manifest, summaries, artifact references and public limits.
2. Acquire all artifacts needed for promised later offline operations, including
   spatial grids needed for Reference/spatial exploration. Validate transfer integrity
   before publication. Summary-first Client loading remains lazy; durable local grid
   availability does not require eager array decoding or retention in RAM.
3. Atomically commit the Client-supported durable format's completeness/publication
   mechanism only after its required local artifacts are safely readable. The current
   v2 format writes its manifest marker last; that is an existing format rule, not a
   required mechanism for every future format. Expose an `IqaResultSource` only after
   committed publication. Never overwrite a different result under a remembered
   identity. Interrupted acquisition leaves no apparently complete bundle. Repeated
   acquisition of the same identity verifies existing data.
4. `IqaResultAccessPort.open_result()` opens a materialized source independently of the
   execution lifetime. History remembers the local reference and expected
   result/schema identity; no live job handle or auth token is required to reopen.
   Identity mismatch is rejected before presentation.
5. After closing/restarting and disconnecting Enterprise execution/storage access,
   reopen summaries, Reference and local grids from the bundle. Optional native source
   Inspect may be unavailable if originals were not retained; result-only exploration
   must still work. Source-retention requirements are declared separately from a result
   bundle's completeness.

The confirmed workflow is local retrieval and known-result reopen. Server-wide
historical inventory/query is not required and must not become a hidden dependency.

## Source resolver boundary

The public seam now defines `IqaSourceLocator`, `IqaResolvedSource` and
`IqaSourceResolutionOutcome`. SUB resolves company-neutral identity into an accessible
client-local path or explicit `MISSING` / `FAILED` outcome; internal storage topology
must not appear in the locator or diagnostic. A local path returned on success is
valid local access data, not a leaked server path or portable source identity.

Resolution and decoding are separate responsibilities. Base retains supported image
decoding and Viewer authority; Client retains inspection policy, expected hash and
dimension checks, alias binding, scene/grid geometry, and stale suppression. Resolution
does not bypass those checks. Changing private mappings invalidates old resolutions;
late work cannot bind an old source to a newer result or intent. Passive result browsing
does not resolve/decode originals or mutate Files/Selection/Primary/Difference/residency.

Existing `remote/iqa_scene_inspection.py` verifies source identities through current
settings; `remote/iqa_history.py` preserves result identity. Their storage coupling is
characterized, not prescribed as SUB's public resolver contract. Offline local result
reopen cannot depend on a shared-root mapping or successful source resolution.

## Authentication and configuration ownership

SUB ships enterprise server/storage defaults and permitted overrides, validates them,
and owns credential acquisition, authorization, renewal, expiry and sign-out. The
Client receives only capabilities and sanitized operational outcomes needed for UI.
No secret, SSO object, internal URL or security protocol crosses the public seam.
Auth replacement by company SSO changes SUB implementation/configuration only.
Existing local normalized bundles remain readable without initiating authentication.

`IqaProviderErrorKind.ACCESS_REQUIRED`, `UNAVAILABLE`, `INVALID`,
`OPERATION_FAILED`, and `AMBIGUOUS_SUBMIT` provide the bounded Client-facing failure
taxonomy. Slice 2 tests verify legacy/private endpoint and payload details are not
forwarded. Interactive credential/SSO acquisition remains SUB responsibility and does
not authorize provider-created Qt UI.

Current schema-v6 Remote IQA settings remain physically in MAIN as characterized.
This contract neither migrates them nor authorizes committing enterprise defaults
there. SUB may use generic supported settings contribution facilities after Slice 4;
secrets and deployment defaults remain SUB-owned. Slice 7 will explicitly address
migration and reset ownership. Do not silently change Base reset semantics during
handoff.

## Upstream pin, allowed paths and sync procedure

`main@bc4090e8e6594089ee47b6dd181700d7ce301482` is the **Slice 2 reconciliation
baseline**, not yet the qualified production deployment pin. The qualified SUB pin is
recorded only after required synthetic coverage, Slice 4 / Checkpoint C, and applicable
Slice 6 enterprise smoke/conformance evidence. Branch names/tags alone are insufficient.
An internal integration record must include MAIN SHA, SUB commit, approved owned-path
manifest, public contract/conformance evidence, enterprise configuration revision and
smoke evidence. Configuration revision identifies an internal artifact without
publishing secrets or endpoints in MAIN.

For a SUB checkout retaining MAIN Git history, use new non-overlapping namespaces
such as the following **proposed ownership allowlist**, adopted in SUB before use:

| SUB-owned addition | Permitted content |
|---|---|
| `src/pixelscope_enterprise/` | Enterprise adapter, resolver, auth/config/transfer implementation and explicit downstream launcher |
| `tests/enterprise/` | Conformance harness adapters, private integration and smoke tests |
| `docs/enterprise/` | Internal deployment, pin/evidence records and operator procedures |
| `enterprise/` | Enterprise configuration templates, internal dependency/packaging/CI overlays; secrets remain in approved private storage |

These are namespace proposals, not new MAIN directories or a required Python API.
If MAIN later introduces a conflicting path, stop sync and resolve ownership upstream.
All inherited paths remain MAIN-owned unless an explicit recorded transfer changes
ownership: particularly `src/pixelscope/**`, existing `tests/**`, `scripts/**`,
root `pyproject.toml`, `requirements/**`, `packaging/**`, `.github/**`, `AGENTS.md`,
and inherited `docs/**`. The table's new SUB namespaces are the only exceptions.
SUB must not edit, shadow with import-path tricks, monkey-patch, weaken tests, or
copy/fork MAIN-owned source to install its provider. Use separate enterprise CI and
build overlays rather than changing upstream workflow/dependency files.

1. On a clean SUB integration branch, record old pin and fetch MAIN upstream; select
   an exact reviewed merged commit. Inspect old-pin to candidate diff and release/
   lifecycle/schema constraints before sync.
2. Prefer ordinary `git fetch upstream` and `git merge <approved-main-sha>` preserving
   history. Resolve conflicts only in SUB-owned content; an upstream-owned conflict
   is a contract defect to fix in MAIN, then consume its merged resolution. Never
   permanently preserve an integration patch in upstream-owned files.
3. When network transfer is unavailable, verify an approved `git bundle` and fetch its
   advertised ref into SUB; require the exact expected MAIN SHA to be present before
   merge. Record bundle provenance/integrity in the internal transfer record.
4. `format-patch` / `git am` is a fallback only for a representable reviewed commit
   range. It can change commit IDs and omit merge topology: retain a source-to-applied
   mapping and verify the upstream-owned resulting tree against the advertised MAIN
   SHA via an independently supplied tree/integrity record. Do not call an applied
   downstream SHA the original MAIN SHA or claim exact-pin equivalence without proof.
5. Compare the candidate MAIN tree to the integrated tree, allowing only the recorded
   SUB-owned additions/changes. Run conformance, applicable upstream canaries and SUB
   smoke. Advance the approved pin only after evidence passes; otherwise retain the
   previous qualified deployment and diagnose on the integration branch.

Generic deficiencies are reported publicly as sanitized semantic requirements and
fixed in MAIN. No private raw payload, credential or internal path is transferred
back. Sync and contract compatibility are tested at each pin, without adding a general
plugin/version-negotiation mechanism.

## Provider contract-conformance validation plan

Merged Slice 2 maps the downstream requirements to concrete public symbols. MAIN owns
`tests/unit/test_iqa_public_contract.py` as the initial deterministic seam evidence;
SUB must run equivalent conformance assertions against its implementation plus private
adapter/transport/storage/auth tests. No confidential fixtures enter MAIN.

| Contract | Merged Slice 2 authority | Required downstream evidence and failure cases |
|---|---|---|
| Execution | `IqaExecutionPort`, `IqaSubmissionIntent`, `IqaJobReference`, `IqaJobSnapshot`, `IqaExecutionCapabilities` | Stable identity; queued/running/terminal transitions; unknown progress; capability-aware cancel; zero-success no result; duplicate/out-of-order completion. |
| Provider failures | `IqaProviderError`, `IqaProviderErrorKind` | Sanitized invalid/unavailable/access/operation failures; retryability; `AMBIGUOUS_SUBMIT` never blindly retried; no endpoint/payload/credential leakage. |
| Result/artifact access | `IqaResultAccessPort`, `IqaResultReference`, `IqaResultSourceOutcome`, `IqaResultOpenOutcome` | Terminal execution survives artifact failure; retry without resubmit; identity-bound publication; interrupted/corrupt/oversized/traversal artifacts rejected. |
| Normalized domain | `IqaResult`, `IqaResultCompleteness`, `IqaAvailability`, `IqaMeasurementSummary`, `IqaDiagnostic` | Same Client behavior for fixture and Enterprise adaptation; ordered IDs/cardinalities, metric semantics, completeness, reference math and geometry preserved; no fabricated missing values. |
| Spatial | `IqaSpatialAccess`, `IqaSpatialLoadOutcome` | Lazy scene/grid acquisition, explicit failed/partial state, offline promised-grid availability without eager RAM retention. |
| Resolver | `IqaSourceLocator`, `IqaSourceResolutionOutcome`, `IqaResolvedSource` | Available/missing/failed distinction, verified local access, identity/dimensions/alias checks, changed-mapping stale resolution, result-only browsing when originals are absent. |
| In-process concurrency | Port docstrings require same-instance overlap safety | Overlapping status/result/cancel and materialize/open/resolve/spatial work; shared backend resources safe; operation/cancel/shutdown-release races have no cross-job/result mix-up, use-after-release, deadlock or stale UI publication. |
| Auth/config | Public error taxonomy only; implementation remains outside the seam | Enterprise defaults/overrides private; expiry/access-required sanitized; SSO substitution does not alter Client contract; local reopen does not initiate auth. |
| Cleanup/sync | Downstream contract; no public deletion API | Owned-resource-only repeated cleanup, failure recovery, active-job preservation; exact MAIN pin and no unapproved upstream-owned diffs. |

Reuse the characterization's domain/partial/source/history tests and
`tests/unit/test_application_composition.py`,
`tests/unit/test_qt_lifecycle_architecture.py`, and owner-local
`tests/ui/test_issue81_qt_lifecycle.py` when implementation touches those contracts.
Hosted CI runs small deterministic contract groups and broad cheap static checks;
Qt timing/geometry/native teardown remains owner-local Windows authority. Do not add
the complete pytest suite to CI. Applicable PR validation, including focused owner-local
canaries required by the changed contract, is the default merge evidence for bounded,
low-risk changes accepted under [QUALITY.md](QUALITY.md). Run full local validation
when that policy requires it for milestone/high-risk/shared-infrastructure/native-
lifecycle work or a repository-wide clean claim; do not require it for every handoff
PR. Focused hosted CI does not replace applicable owner/local lifecycle evidence, and
neither focused nor full repository validation proves enterprise infrastructure.

## Minimum production smoke plan (SUB, not yet executed)

Prerequisites: merged/reconciled Slice 2, synthetic coverage/Checkpoint B, Slice 4 and
Checkpoint C; approved MAIN pin and SUB-owned launcher; approved real GPU/auth/shared
storage with a permitted input pair and retained evidence destination. Use CPython
3.10 x64 and current lifecycle constraints; no packaging-tool run is implied.

1. Launch **Base + unchanged IQA Client + real Enterprise adapter**. Record MAIN/SUB
   SHAs and internal configuration revision. Open IQA actions/dock and select a pair
   of local files requiring staging. Confirm selection/viewer state remains correct.
2. Authenticate through SUB, stage verified inputs, submit once and observe real queue/
   execution/completion. Capture stable public job/result identities and sanitized
   state evidence, with internal transport evidence kept only in SUB.
3. Download/adapt/publish the local normalized bundle. Explicitly open it through the
   Client; check dataset/scene/variant/attribute identities, expected scalar values,
   Reference switching and lazy spatial-grid exploration. Inspect a resolvable source
   through Base and verify source identity/geometry.
4. Verify remote cleanup follows retention and affects only owned resources after
   durable publication. Close the app cleanly. Disable execution/shared-storage access
   and restart; open the saved local result without a live job/auth session. Confirm
   summaries, Reference and grids work; missing originals yield result-only browsing.
5. Record one additional controlled partial/missing case and a failed or interrupted
   transfer recovery; show no false COMPLETE, no duplicate submit and no premature
   cleanup. Exercise unsupported cancel or supported cancel according to capability.
   Check close while waiting rejects late UI publication and preserves the durable job.

PASS requires the whole primary real flow plus recorded applicable negative checks,
clean shutdown and upstream-owned tree verification. Synthetic/loopback or a server
with no real computation is not production PASS. Retain timestamp/environment,
identities, observed outcomes, cleanup disposition and operator sign-off internally;
report only sanitized pass/fail and semantic gaps to MAIN. This smoke does not replace
the broader deferred [P5-G qualification](exec-plans/deferred/p5g-external-gpu-smb-validation.md).

## Slice 2 reconciliation outcome and remaining prerequisites

Merged Slice 2 baseline: `bc4090e8e6594089ee47b6dd181700d7ce301482`.
Focused public seam authority: `src/pixelscope/remote/iqa_public_contract.py`,
`src/pixelscope/remote/iqa_public_adapter.py`, and
`tests/unit/test_iqa_public_contract.py`.

| ID | Reconciled disposition |
|---|---|
| G1 | **Resolved at public-seam level.** Stable `IqaJobReference` / `IqaResultReference`, `IqaJobState`, progress/snapshot, cancel capability, and separate execution/result-access ports represent execution independently from recoverable artifact acquisition. |
| G2 | **Public seam resolved; durable Enterprise materialization evidence remains downstream.** `IqaResultAccessPort.materialize()` returns `IqaResultSourceOutcome` and `open_result()` is execution-independent. Slice 6 must prove actual download/atomic local publication/restart-offline reopen with the Enterprise adapter and agreed Client-readable encoding. |
| G3 | **Core public resolver semantics resolved.** `IqaSourceLocator` + `IqaSourceResolutionOutcome` explicitly distinguish AVAILABLE/MISSING/FAILED and only expose a local path on success. Existing Client stale/identity checks remain authoritative; changing private mapping behavior is a SUB conformance/Slice 4 integration concern, not a new public path API. |
| G4 | **Public in-memory semantics resolved; durable encoding edge remains explicit.** `IqaAvailability`, `IqaMeasurementSummary`, diagnostics and lazy spatial outcomes can represent missing/failed data. Current schema-v2 still does not serialize arbitrary metric-level absence in an otherwise successful scene, so real Enterprise data requiring that case needs a narrow MAIN durable-format decision before transfer qualification. |
| G5 | **Execution cancellation semantics resolved; composition/release evidence remains.** `IqaExecutionCapabilities.can_cancel`, `cancel()`, terminal `IqaJobState`, and provider errors separate capability/failure. Durable remote-job behavior, stale callback rejection and backend release stay frozen by existing lifecycle contracts and require Slice 4/Checkpoint C evidence. |
| G6 | **Resolved at public-seam level.** `IqaProviderErrorKind` bounds ACCESS_REQUIRED/UNAVAILABLE/INVALID/OPERATION_FAILED/AMBIGUOUS_SUBMIT, and tests verify provider detail is sanitized. SSO/credential mechanics remain wholly SUB-owned. |
| G7 | **Intentionally open for Slice 4.** Public ports exist, but approved Base/IQA Client composition/injection is not yet changed. SUB must not patch/shadow MAIN while this remains open. Checkpoint C closes the integration prerequisite. |
| G8 | **Concurrency contract resolved; Enterprise conformance remains.** Both public ports require same-instance overlap safety; `IqaSpatialAccess` is concurrent-safe. The P5 adapter demonstrates internal serialization for a legacy client and focused tests exercise concurrent execution calls. SUB must prove its own overlapping execution/result/resolver/transfer and shutdown-release safety. |

No remaining Slice 2 semantic mismatch blocks merging this Slice 5 documentation
contract. This does **not** mean the system is transfer-ready: G7, Checkpoint B/C,
Enterprise durable materialization/conformance/smoke evidence, and any real G4 durable-
encoding case remain explicit prerequisites. Slice 6 supplies real SUB evidence;
settings cleanup and optional Stage 2/package work remain later Slice 7/8 scope.
