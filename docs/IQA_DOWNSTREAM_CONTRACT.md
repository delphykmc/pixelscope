# IQA downstream consumer and transfer contract

Status: **Slice 5 draft; awaiting merged Slice 2 reconciliation**. This is a semantic
consumer contract, not an implemented provider API or transfer-ready sign-off.
Draft baseline: `main@4aa1915ff78eefea24458e15837a40a45fcb4670` (Slice 1).
Last updated: 2026-10-05.

## Authority and scope

Read [Issue #121](https://github.com/delphykmc/pixelscope/issues/121), its
[confirmed Checkpoint A](https://github.com/delphykmc/pixelscope/issues/121#issuecomment-5993880778),
merged [Slice 0 / PR #122](https://github.com/delphykmc/pixelscope/pull/122),
merged [Slice 1 / PR #123](https://github.com/delphykmc/pixelscope/pull/123),
[IQA ownership](IQA_OWNERSHIP.md), and
[boundary characterization](IQA_BOUNDARY_CHARACTERIZATION.md) as the authority.
Checkpoint A confirms the intended enterprise workflow; characterization freezes
existing behavior and lifetime constraints rather than the historical transport API.

SUB must supply Enterprise IQA through the Client-owned public seam without changing
MAIN-owned Base or IQA Client source. MAIN remains runnable with public/synthetic data.
Exact Python names, signatures, and injection sites belong to Slice 2 and Slice 4.
References here to execution, artifact access, and resolver describe responsibilities,
not additional protocols that SUB may impose on the Client.

This draft delivers downstream design, transfer policy, and validation plans only.
Confidential implementation, schema conversion code, settings migration, package moves,
SSO implementation, packaging runs, and production integration are out of scope.

## Responsibility boundary

| Concern | Owner and observable obligation |
|---|---|
| Generic host | Base hosts menus/docks/settings, selection/viewer access, workers and lifecycle primitives. It does not own IQA semantics. |
| IQA Client | MAIN owns IQA actions/dock, submission intent, job/result presentation, normalized result/domain, history, reference/scene selection, lazy grid requests, generation/stale-result rejection. |
| Execution/control | SUB authenticates, submits, tracks queue/execution, adapts completion/failure, and implements optional backend cancellation. |
| Artifact/data | SUB stages local inputs, accesses published artifacts, transfers and normalizes results, resolves sources, and manages remote retention/cleanup. |
| Composition | SUB's explicit launcher supplies Enterprise implementations through merged public seams; Client/Base retain their existing resource ownership. No runtime discovery framework is required. |
| Enterprise configuration | SUB owns endpoint defaults/overrides, storage topology, auth/security, backend schemas, deployment and internal evidence. |

Dependencies remain `Enterprise IQA -> IQA Client -> Base`. Providers supply plain
data/non-UI operations and do not create QWidget/QObject/QThreadPool objects merely
to provide IQA. Client scheduling stays off the UI thread using existing resource
domains. A provider owns its non-Qt backend resources and deterministic release;
release must be idempotent and must not rely on cyclic GC or retain a UI owner.
Existing startup/install order, pool identities/cardinality, and close semantics in
the characterization remain protected. Missing injection capability is an upstream
gap, not permission to patch a window/controller downstream.

### Provider call concurrency — pending reconciliation

Existing Client-owned result/file and job-operation pools can execute overlapping
work; concurrent-user storage isolation alone does not define in-process safety.
Slice 2/4 reconciliation must record which execution, result/artifact and resolver
operations can overlap on the same provider/port instance, including status/result/
cancel and result/resolver work, and which non-Qt backend resources are shared.

If one instance receives concurrent calls, SUB must provide the documented thread-safe,
reentrant behavior, including races with cancellation and backend release. If public
composition guarantees separate port instances or explicit serialization instead,
record that guarantee and its owner in MAIN, and identify any resources still shared
between instances. Neither model is selected by this draft; G8 blocks reliance on an
unverified serial-call assumption. Preserve existing pool ownership/cardinality and
off-thread work; no new pool, UI-thread serialization, or lifecycle redesign is implied.

## Control plane flow

1. Client captures a public submit intent from the underlying current pair or the
   supported folder/path workflow. Existing eligibility, pair ordering, source
   identity, and bounds remain unchanged. Presentation state is not request authority.
2. Enterprise validates its configuration/access and stages the inputs before remote
   acceptance. It translates the intent to its private request representation.
3. Submission yields a stable public job reference with authority scoped to that
   user's work. Backend identifiers and topology remain private implementation data.
   Never blindly retry a possibly accepted create. Report an ambiguous outcome as
   actionable uncertainty; reconcile privately if supported, without duplicate work.
4. Adapt queued/running and terminal completion/failure into public state/progress and
   bounded sanitized messages. Unknown progress is not fabricated as a percentage.
   Optional cancellation is exposed only when meaningful and supported; unsupported
   cancel is distinguishable from cancellation failure.
5. Socket notifications, polling, HTTP and reconnection are Enterprise details. A
   duplicate, delayed or reordered notification cannot regress a terminal state,
   attach another job's result, or publish into a revoked Client generation. The
   Enterprise implementation reconciles notification claims with its own authority.
6. Successful/partial execution supplies a stable public result reference. Remote
   execution completion does not imply that local download/normalization succeeded.
   Artifact acquisition failures stay recoverable without resubmission and without
   rewriting the terminal execution outcome. Zero-success/failed/cancelled work does
   not provide an openable result. Completion never automatically opens Results.

Client close revokes UI publication and cancels pending Client work; it does not imply
remote cancellation of a durable job. Enterprise must honor cooperative abort before
remote acceptance, release backend resources on shutdown, and leave server-owned jobs
and their required inputs intact. Cancellation of local waiting/transfer is distinct
from cancelling server execution and from deleting remote artifacts.

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

Enterprise adapts proprietary responses into the **same Client-owned domain** used by
MAIN synthetic fixtures. Preserve stable result identity, dataset metadata, ordered
scenes/variants/attributes, labels, scalar/per-scene values, value kind/direction/range,
measurement context, source bindings, completeness and sanitized diagnostics. Private
schema fields, credentials, internal endpoints and raw payloads stay in SUB.

Missing scene/metric values come from authoritative completeness information. Do not
silently drop them, replace them with zero, or claim a complete result. The current
[schema-v2 contract](REMOTE_IQA_V2_SPEC.md) requires fully shaped successful scenes;
PARTIAL records every requested scene outcome and excludes failed/cancelled scenes
from numerical summaries. It is not a general arbitrary missing-metric schema.
Represent invalid measurements only where the canonical domain permits it. If a real
metric absence cannot be represented faithfully, report G4 below before transfer;
do not relax the reader or invent downstream-only numerical semantics.

The existing `remote/iqa_result_reader.py` is the canonical versioned loader;
`remote/iqa_v2_domain.py` and canonical reader/math define current numerical meaning.
A direct normalized domain result must retain that meaning. Durable serialization
must be a Client-readable supported format agreed after Slice 2, with schema-v1 kept
read-only. No parallel Enterprise numerical engine is introduced into Client code.

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
   required mechanism for every format reconciled with Slice 2. Expose the local
   reference only after committed publication. Never overwrite a different
   result under a remembered identity. Interrupted acquisition leaves no apparently
   complete bundle. Repeated acquisition of the same identity verifies existing data.
4. Explicit Open Result uses the normal Client path. History captures the local
   reference and expected result/schema identity; no live job handle or auth token is
   required to reopen. Identity mismatch is rejected before presentation.
5. After closing/restarting and disconnecting Enterprise execution/storage access,
   reopen summaries, Reference and local grids from the bundle. Optional native
   source Inspect may be unavailable if originals were not retained; result-only
   exploration must still work. Source-retention requirements are declared separately
   from a result bundle's completeness.

The confirmed workflow is local retrieval and known-result reopen. Server-wide
historical inventory/query is not required and must not become a hidden dependency.

## Source resolver boundary

The Client requests a source using company-neutral identity/locator metadata plus
result/scene/variant context. SUB resolves that identity into an accessible client-local
source or an explicit unavailable/failure outcome; it may map, retrieve or reuse data
privately. A local filesystem path returned for Base image opening is valid local
access data, not a leaked server path or portable source identity. No UNC/server-root
convention is required by the port or committed into MAIN examples.

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

If interactive access is necessary, SUB's launcher or separately approved enterprise
integration owns it. Do not require a provider call to construct Qt UI or hide a new
authentication UI/thread model inside this draft. Required access must be distinguishable
from unsupported capability or transport failure in public outcome semantics.

Current schema-v6 Remote IQA settings remain physically in MAIN as characterized.
This draft neither migrates them nor authorizes committing enterprise defaults there.
SUB may use generic supported settings contribution facilities after Slice 4; secrets
and deployment defaults remain SUB-owned. Slice 7 will explicitly address migration
and reset ownership. Do not silently change Base reset semantics during handoff.

## Upstream pin, allowed paths and sync procedure

The draft baseline above is **not** a qualified production upstream pin. SUB records
the exact merged MAIN commit SHA after Slice 2 reconciliation, required synthetic
coverage and Checkpoint C. Branch names/tags alone are insufficient. An internal
integration record must include MAIN SHA, SUB commit, approved owned-path manifest,
public contract/conformance evidence, enterprise configuration revision and smoke
evidence. Configuration revision identifies an internal artifact without publishing
secrets or endpoints in MAIN.

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

After Slice 2 merges, map each row to its actual public seam and reusable synthetic
fixtures. MAIN owns deterministic public assertions; SUB runs those assertions against
its implementation plus private adapter/transport tests. No confidential fixtures enter
MAIN. Names of new tests are deferred until reconciliation.

| Contract | Required evidence and failure cases |
|---|---|
| Execution | Stable job identity; queued/running/terminal transitions; unknown progress; optional cancel; zero-success no result; duplicate/out-of-order completion; ambiguous create never blindly retried. |
| Transfer | Terminal execution survives artifact failure; retry without resubmit; identity-bound publication; interrupted/corrupt/oversized/traversal artifacts rejected; concurrent-user isolation. |
| Normalized domain | Same Client behavior for fixture and Enterprise adaptation; ordered IDs/cardinalities, metric semantics, completeness, reference math and geometry preserved; no fabricated missing values. |
| Materialization | Atomic local publication; full promised offline artifact availability; independent restart/reopen; mismatch rejected; no auth/network required to browse local summaries/Reference/grids. |
| Resolver | Available/unavailable/error, identity/dimensions/alias checks, changed-mapping stale resolution, optional source absence with result-only browsing. |
| Lifecycle | Qt-free supply; existing pools/order; revoke stale authority; idempotent backend release; close does not remote-cancel jobs or delete live inputs. |
| In-process concurrency | Overlapping status/result/cancel and result/resolver operations under the reconciled same-instance, separate-instance or serialized model; shared backend resources remain safe. Exercise operation/cancel/shutdown-release races with deterministic synchronization; verify no cross-job/result identity mix-up, use-after-release, deadlock or stale UI publication. If serialization/isolation is promised, prove composition enforces it rather than testing only serial calls. |
| Auth/config | Enterprise defaults/overrides private; expiry/access-required sanitized; SSO substitution does not alter Client contract; local reopen does not initiate auth. |
| Cleanup/sync | Owned-resource-only repeated cleanup, failure recovery, active job preservation; exact MAIN pin and no unapproved upstream-owned diffs. |

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

Prerequisites: reconciled Slice 2, synthetic coverage/Checkpoint B, Slice 4 and
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

## Required semantic gaps for Slice 2 reconciliation

These are **required semantic gap candidates against the merged Slice 1 baseline**,
not claims that the parallel Slice 2 implementation is defective. No gap is resolved
merely because this draft describes it. Map each to merged code/tests, or record an
upstream follow-up with an owner and block the affected handoff flow.

| ID | Required semantic / acceptance evidence | Current disposition |
|---|---|---|
| G1 | Stable job/result references, capability-aware cancel, sanitized public states; terminal execution distinct from recoverable artifact acquisition. | Await Slice 2 execution/artifact mapping. |
| G2 | Independently materialized normalized result, supported durable encoding and local reference; restart/offline reopen including Reference and lazy grids without provider session. | Await Slice 2 result-source mapping; current canonical local loader is evidence, not a new API. |
| G3 | Company-neutral source resolution with explicit unavailable/error and verified local access; identity and mapping-revision stale behavior preserved. | Await Slice 2 resolver mapping; current root-settings coupling cannot be prescribed downstream. |
| G4 | Explicit manifest-derived scene/metric absence and completeness, without fabricated zeros or relaxed successful-scene invariants. | Reconcile against canonical v2 constraints; unsupported metric absence requires a narrow MAIN decision before real adaptation. |
| G5 | Cancellation/release semantics distinguish local abort, durable remote job cancellation and retention; late callbacks cannot mutate disposed UI. | Await Slice 2 tests against frozen lifecycle. |
| G6 | Provider-owned access/config failure conveyed without exposing auth objects/endpoints; SSO swap leaves public consumers unchanged. | Await Slice 2 public outcome mapping; enterprise implementation stays in SUB. |
| G7 | Explicit composition can supply execution, artifact and resolver responsibilities without modifying/shadowing MAIN-owned source or creating provider Qt ownership. | Slice 2 seam plus Slice 4 injection/Checkpoint C; draft cannot sign off early. |
| G8 | Define overlapping calls per provider/port instance and shared resources: SUB thread-safe/reentrant implementation, or MAIN-owned separate-instance/explicit-serialization guarantees. Prove overlapping operation/cancel/shutdown-release race safety under existing pools. | Await Slice 2/4 concurrency model and conformance mapping; no serial-call assumption permitted before reconciliation. |

Reconciliation updates this document with the merged Slice 2 SHA, exact public symbols
and focused test references, supported limitations, and each gap's resolution or
explicit blocker. Final Slice 5 sign-off also requires the transfer evidence/Checkpoint
C prerequisites. Slice 6 supplies real SUB evidence; settings cleanup and optional
Stage 2/package work remain later Slice 7/8 scope.
