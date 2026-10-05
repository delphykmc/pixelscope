# Execution plan: Issue #121 Slice 5 downstream transfer contract

Status: Draft — awaiting merged Slice 2 reconciliation
Owner: Slice 5 downstream/SUB integration contract agent
Branch: `codex/issue-121-slice5`
Last updated: 2026-10-05

## Goal and scope

Define how SUB supplies Enterprise IQA to unchanged MAIN Base/IQA Client through the
Client-owned public seam. Deliver a reviewable semantic contract, upstream pin/sync
and path policy, conformance/smoke plans, and explicit Slice 2 gap candidates.

No runtime code, confidential implementation, parallel public API, settings migration,
package move, packaging run or production integration is included. Slice 2 proceeds
separately; dependent production work waits for its merge and reconciliation.

## Current state and authority

Baseline `main@4aa1915ff78eefea24458e15837a40a45fcb4670` contains merged Slice 0/1.
The confirmed [Checkpoint A](https://github.com/delphykmc/pixelscope/issues/121#issuecomment-5993880778)
defines the enterprise execution/shared-storage/local-reopen workflow.
[Ownership](../../IQA_OWNERSHIP.md) and
[characterization](../../IQA_BOUNDARY_CHARACTERIZATION.md) remain authoritative.
Current canonical result reader/domain, history and scene inspection were inspected;
their existing transport/settings coupling does not freeze the public seam.

## Design and invariants

The focused [downstream contract](../../IQA_DOWNSTREAM_CONTRACT.md) owns this design.
Enterprise owns control/data/auth/config/normalization/cleanup. Client owns IQA
presentation/domain and stale publication authority. Base owns generic host services.
Preserve dependency direction, pool ownership/order, durable remote jobs, CPython
3.10 x64 and existing numerical/result/Qt lifetime contracts.

## Work and acceptance gates

1. Read Issue #121 in full, latest Checkpoint A, merged #122/#123 and relevant docs.
2. Draft downstream responsibilities, transaction/failure flows, pin/path/sync policy,
   conformance matrix and real smoke plan; enumerate G1-G8 semantic gap candidates.
3. Validate docs and diff preservation, create a ChatGPT-assisted draft PR, report
   observed local/hosted results. Draft delivery does not close Issue #121.
4. Wait for merged Slice 2. Map G1-G8 to actual symbols/tests; resolve gaps upstream
   or record blockers before any dependent implementation or transfer sign-off.
5. Finalize Slice 5 after Slice 4/Checkpoint C; Slice 6 executes real SUB validation.

## Validation plan

Run `scripts/check_docs.py`, `tests/unit/test_docs_contract.py`, broad Ruff lint/format,
mypy and `git diff --check` under applicable documentation-only PR scope. Inspect
baseline-to-head diff/deletion counts and semantic coverage. Hosted CI follows existing
change-driven policy; no full pytest or Qt suite is added. No runtime/manual production
or GPU/SMB PASS is claimed. Full local suite is not required for this bounded draft.

## Risks and mitigations

| Risk | Detection / mitigation |
|---|---|
| Unmerged API assumed final | Semantic requirements only; mandatory merged-Slice-2 reconciliation table. |
| Missing metric falsely normalized | G4 requires faithful completeness and canonical v2 rules; block unsupported conversion. |
| Close/cleanup loses durable work | Separate UI abort, remote cancel and retention; test owned resources and late results. |
| Permanent SUB patch drift | Owned-path allowlist and exact upstream-tree comparison at every pin. |
| Confidential information leak | Company-neutral MAIN requirements/fixtures; private implementation/evidence stays SUB. |

## Progress and evidence

- 2026-10-05: Authoritative sources read; isolated in-repository worktree created for
  Slice 5 to avoid interfering with parallel Slice 2. Semantic draft and G1-G7 recorded.
- 2026-10-05: Local `scripts/check_docs.py`: `Documentation contract passed.`;
  `pytest -q tests/unit/test_docs_contract.py`: `2 passed in 0.31s`; Ruff lint
  succeeded, Ruff format: `408 files already formatted`; mypy: `Success: no issues
  found in 140 source files`; `git diff --check`: exit 0. Existing durable-doc
  changes are additive routing links only. Hosted PR CI on `7ef1a52` subsequently
  passed Change-scoped validation and Ubuntu/Windows User Guide validation; evidence
  is recorded in PR #124.
- 2026-10-05: PR #124 review follow-up aligns validation with QUALITY's applicable
  PR/full-validation conditions, adds G8 provider call concurrency reconciliation and
  overlap/cancel/shutdown conformance, and makes durable publication format-neutral.
  No concurrency model or new public API is selected; runtime remains unchanged.
- 2026-10-05: Review-fix local checks: documentation contract passed;
  `pytest -q tests/unit/test_docs_contract.py`: `2 passed in 0.45s`; Ruff lint exit 0;
  Ruff format: `408 files already formatted`; mypy: `Success: no issues found in
  140 source files`; diff check exit 0. Latest-head hosted CI will be reported in PR #124.

## Completion / deferred work

Draft files: `docs/IQA_DOWNSTREAM_CONTRACT.md`, this execution plan, and narrow routing
links in `docs/index.md` and `docs/IQA_OWNERSHIP.md`. Runtime behavior is unchanged.
Final contract reconciliation, Slice 4 injection evidence, production smoke and
internal pin qualification remain unverified. Keep this plan Draft until reconciliation;
no automatic production work is authorized by its publication.
