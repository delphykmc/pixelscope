# Execution plan: Issue #121 Slice 5 downstream transfer contract

Status: Complete — contract reconciled with merged Slice 2; transfer qualification remains downstream
Owner: Slice 5 downstream/SUB integration contract agent
Branch/PR: `codex/issue-121-slice5` / PR #124
Last updated: 2026-10-05

## Goal and scope

Define how SUB supplies Enterprise IQA to unchanged MAIN Base/IQA Client through the
Client-owned public seam. Deliver a reviewable semantic contract, upstream pin/sync
and path policy, conformance/smoke plans, and explicit downstream prerequisites.

No runtime code, confidential implementation, parallel public API, settings migration,
package move, packaging run or production integration is included. Slice 2 is now
merged and reconciled. Actual provider injection waits for Slice 4/Checkpoint C and
real Enterprise qualification belongs to Slice 6.

## Current state and authority

Reconciliation baseline `main@bc4090e8e6594089ee47b6dd181700d7ce301482`
contains merged Slice 0/1/2, including PR #125's Qt-free public IQA Client seam.
The confirmed [Checkpoint A](https://github.com/delphykmc/pixelscope/issues/121#issuecomment-5993880778)
defines the enterprise execution/shared-storage/local-reopen workflow.
[Ownership](../../iqa/IQA_OWNERSHIP.md),
[characterization](../../iqa/legacy/IQA_BOUNDARY_CHARACTERIZATION.md), and the focused
[downstream contract](../../iqa/IQA_DOWNSTREAM_CONTRACT.md) were the contemporary authority for this completed Slice 5 plan; the current implementation authority is [IQA documentation](../../iqa/README.md).

Merged Slice 2 provides `IqaExecutionPort`, `IqaResultAccessPort`, normalized
`IqaResult`, lazy `IqaSpatialAccess`, provider-neutral errors, explicit source outcomes,
and same-instance concurrency requirements. Existing P5 adapters prove compatibility
without changing production composition/lifecycle. Slice 4 still owns the approved
injection seam.

## Design and invariants

Enterprise owns control/data/auth/config/normalization/cleanup. Client owns IQA
presentation/domain and stale publication authority. Base owns generic host services.
Preserve dependency direction, pool ownership/order, durable remote jobs, CPython
3.10 x64 and existing numerical/result/Qt lifetime contracts.

Public-provider calls may overlap on the same instance. SUB implementations must be
thread-safe/reentrant or internally serialize their own non-Qt resources; Client
composition does not promise per-instance serialization. No new worker pool or Qt
ownership is introduced by this contract.

## Work and acceptance gates

1. Read Issue #121 in full, latest Checkpoint A, merged #122/#123 and relevant docs.
2. Draft downstream responsibilities, transaction/failure flows, pin/path/sync policy,
   conformance matrix and real smoke plan; enumerate G1-G8 reconciliation candidates.
3. Validate docs and diff preservation, create PR #124, collect hosted review/CI and
   resolve validation/concurrency/publication review findings.
4. **Completed:** reconcile G1-G8 against merged Slice 2 / PR #125 actual symbols and
   tests. Record which semantics are resolved and which are intentionally deferred to
   Slice 4/Checkpoint C or real SUB qualification.
5. Merge this documentation contract once the reconciliation diff and applicable CI
   pass. Slice 4/Checkpoint C then establishes transfer-ready composition; Slice 6
   executes real SUB validation. Merging Slice 5 is not production qualification.

## Validation plan

For this bounded documentation PR run `scripts/check_docs.py`,
`tests/unit/test_docs_contract.py`, broad Ruff lint/format, mypy and `git diff --check`
under the current change-driven policy. Inspect baseline-to-head diff and semantic
coverage. No full pytest or Qt suite is added to hosted CI.

Slice 2 itself has separate focused/public-contract validation and owner-reported full
suite PASS. That evidence supports the merged seam but is not re-run merely because
Slice 5 documentation maps to it. Future runtime/composition changes follow
`docs/QUALITY.md`: applicable focused owner-local canaries are required, and full local
validation is used when the policy requires milestone/high-risk/shared-infrastructure/
native-lifecycle or repository-wide-clean evidence.

No documentation validation or MAIN full suite constitutes real GPU/storage/auth/SUB
integration PASS.

## Risks and mitigations

| Risk | Detection / mitigation |
|---|---|
| Downstream doc drifts from public API | Reconciled table names merged Slice 2 symbols and baseline SHA; review at every upstream pin. |
| Missing metric falsely normalized | Public in-memory missing/failure semantics exist, but current v2 durable-format limitation remains explicit; block unsupported conversion pending narrow MAIN decision. |
| Close/cleanup loses durable work | Separate UI abort, remote cancel and retention; preserve existing lifecycle and test owned resources/late results at Checkpoint C/Slice 6. |
| Same provider instance races | Public ports require overlap safety; SUB conformance exercises status/result/cancel, materialize/open/resolve/spatial and release races. |
| Permanent SUB patch drift | Owned-path allowlist and exact upstream-tree comparison at every pin. |
| Confidential information leak | Company-neutral MAIN requirements/fixtures; private implementation/evidence stays SUB. |

## Progress and evidence

- 2026-10-05: Authoritative sources read; isolated in-repository worktree created for
  Slice 5 to avoid interfering with parallel Slice 2. Semantic draft and G1-G7 recorded.
- 2026-10-05: Initial local docs checks passed; hosted Change-scoped validation and
  Ubuntu/Windows User Guide validation passed on the draft.
- 2026-10-05: PR #124 review follow-up aligned validation with `QUALITY.md`, added G8
  concurrency reconciliation/overlap-release conformance, and made durable publication
  format-neutral. Re-review found no architecture/runtime blocker while awaiting Slice 2.
- 2026-10-05: Slice 2 / PR #125 reached merge-ready after resolving public error
  semantics, explicit source outcomes, same-instance concurrency and explorer typing.
  Owner additionally reported repository full-suite PASS. PR #125 was squash-merged as
  `bc4090e8e6594089ee47b6dd181700d7ce301482`.
- 2026-10-05: Slice 5 reconciled against merged public symbols/tests. G1/G6 and the
  public portions of G3/G8 are resolved; G2/G4/G5 retain explicit downstream/runtime
  evidence requirements; G7 remains intentionally owned by Slice 4/Checkpoint C. No
  Slice 2 semantic mismatch remains that blocks merging this documentation contract.

## Completion summary

- Delivered behavior: no runtime change; established the downstream Enterprise
  ownership/transfer/conformance contract and reconciled it to the actual merged
  Client-owned public seam.
- Changed files: `docs/IQA_DOWNSTREAM_CONTRACT.md`, this completed execution plan, and
  narrow routing links in `docs/index.md` / `docs/IQA_OWNERSHIP.md`.
- Validation: documentation/static checks and hosted docs workflows are required for
  the final reconciliation head before merge.
- Remaining limitations: Slice 4 injection/Checkpoint C, real Enterprise adapter,
  durable materialization/cleanup/auth/storage conformance, production smoke, and any
  real metric-level missing-data durable encoding case remain unqualified.
- Follow-up: Slice 6 supplies real SUB evidence; Slice 7 owns settings migration;
  Slice 8 remains optional Stage 2/package cleanup.

The plan is complete as a **documentation/contract slice**. Its remaining prerequisites
belong to later Issue #121 slices and must not be interpreted as production PASS.
