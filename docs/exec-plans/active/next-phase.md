# Execution plan: R — Repository Refactoring & Validation Hardening

Status: Active — **R6 independent review PASS / merge pending**
Owner: repository owner + refactoring implementation/review agents
Branch/PR: `codex/r6-harness-architecture-guardrails` / #54
Last updated: 2026-08-24

## Goal

Simplify PixelScope's repository structure, make dependency/resource ownership explicit,
and improve validation reliability without changing product behavior, numerical
semantics, persisted contracts, compatibility, or history. Completion is observed as a
sequence of small independently reviewed PRs, followed by exact final repository gates
and a durable closeout record.

This program is named **R**, not P6. P6 remains the future Identity, Access & Remote
Operations product program. P5-G remains a deferred external GPU/SMB validation gate.

## Scope

### In scope

- current-state and harness reconciliation;
- application/controller composition seams;
- worker/executor/resource ownership clarity;
- bounded generation/revision/stale-work cleanup where it demonstrably simplifies code;
- obsolete compatibility scaffold and duplicated helper review;
- test fixture/suite organization and Windows offscreen hardening;
- durable documentation and mechanical architecture/validation guardrails;
- final integration validation and closeout.

### Out of scope

- new UI/UX or IQA calculations;
- schema, Session format, numerical, source, residency, cache, preload, concurrency,
  retry, polling, or server API policy changes;
- authentication/SSO, credentials, permission policy, or administration;
- real GPU server or SMB integration and any fabricated external PASS;
- a DI framework, service container, generic lifecycle framework, broad MainWindow
  split, or directory reshuffle without demonstrated value.

Behavior-change needs discovered during R are findings/deferred work, not implicit
authorization to implement them.

## Current state

R begins from `main@6634447fc3c48545a2482718dd3f444928806218`, the P5-F / PR #45 merge.
P5-A through P5-F repository-side client work is complete. Overall P5 remains Active
because the real P5-G external GPU/SMB gate is unobserved and deferred in
[`docs/exec-plans/deferred/p5g-external-gpu-smb-validation.md`](../deferred/p5g-external-gpu-smb-validation.md).

At R0 start the GitHub repository is public, the default branch is `main`, and no PR is
open. Repository-owner issue-creation restrictions are operational GitHub policy; R does
not mutate repository visibility, collaboration, issue, or branch-protection settings.

## Non-regression authority

The following contracts are frozen throughout R:

- `Registered → Selected → Current Comparison Page → Presented → Resident`;
- `Analysis Working Set = Current Comparison Page`;
- native `ImageDocument.source` authority;
- Display Gain presentation-only behavior and canonical Difference semantics;
- P2 residency/cache/preload ownership;
- P4 curation, Session v1, Recent, and historical workflow semantics;
- P5 schema-v2 server-measurement/local-comparison authority;
- P5-B canonical IQA Results workspace and reader dispatch;
- P5-C submission/job/shared-storage contracts;
- P5-D explicit native Inspect authority;
- P5-E historical Result authority;
- P5-F bounded worker/transport lifetime contracts;
- schema-v1 read-only and legacy Comparison Set compatibility.

Target remains CPython 3.10 x64 and PyInstaller exactly 5.7 `onedir`. R does not run or
change packaging unless separately authorized.

## Audit findings

No P0 correctness defect was found during the initial repository-wide audit.

### P1 — implicit IQA composition and wrapper order

- Problem: IQA controller installation relies on ordered `install_*` calls,
  `MethodType`, `_original_*` wrappers, signal reconnects, and dynamically attached
  controller attributes.
- Evidence: `src/pixelscope/app/application.py` installs P5 controllers in a fixed
  sequence; seven IQA controller modules contain roughly 27 `MethodType` bindings,
  including the settings-change chain across result mapping, native Inspect, and
  historical Results.
- Impact: dependencies and shutdown/settings ownership are hard to review; reordering a
  seemingly independent installer can silently change behavior.
- Recommended correction: expose the existing order and dependencies through the
  smallest explicit application-owned composition seam; retain controller-local
  behavior and signal/public method contracts.
- Risk: high blast radius if wrapper order or initialization timing changes.
- Proposed slice: R1.

### P1 — correct pool policy, implicit pool injection

- Problem: P5-B/P5-D/P5-E controllers are constructed with the local analysis pool and
  later rebound by direct private `_pool` assignment to the P5-F Remote IQA pool.
- Evidence: production composition in `src/pixelscope/app/application.py` performs the
  rebind after controller installation; the separate local-analysis, Remote-IQA
  file/result, and P5-C job-operation pools otherwise have correct bounded policies.
- Impact: construction-time ownership is misleading and a future installer/test can
  accidentally run remote file work on the wrong pool.
- Recommended correction: make the already-established pool dependency explicit at
  construction/install time; do not change pool counts, cancellation, or shutdown.
- Risk: lifecycle/stale callback regression if cancellation order moves.
- Proposed slice: R2.

### P1 — obsolete pre-P5 Remote scaffold

- Problem: the initial `remote/evaluation_client.py`, `mock_client.py`, and `schemas.py`
  scaffold forms a self-contained `/v1/jobs` contract that is not used by the canonical
  P5 `/v1/iqa/jobs` implementation.
- Evidence: production imports do not reach it; `tests/unit/test_remote.py` only tests
  the scaffold, while current quality text mislabels it as P5-A schema-v1 coverage.
- Impact: two apparent Remote APIs confuse navigation and can be mistaken for supported
  compatibility.
- Recommended correction: confirm history and all imports, then remove only the dead
  scaffold/test while explicitly retaining schema-v1 result compatibility coverage.
- Risk: an undocumented external importer may exist outside the repository.
- Proposed slice: R3-A; removal requires independent compatibility review.

### P1 — Session authority split

- Problem: Comparison Set persistence is divided between a base class, Session subclass,
  and facade, making current Session v1 versus legacy compatibility ownership indirect.
- Evidence: `ui/comparison_set.py`, `ui/session.py`, and their facade/call sites share the
  boundary.
- Impact: persistence refactors are difficult to review and risk accidental legacy or
  Recent behavior changes.
- Recommended correction: document and minimally expose the boundary; consolidate only
  duplicated mechanics proven by tests.
- Risk: persisted-data and transactional restore regression.
- Proposed slice: R3-B.

### P1 — duplicated UI test harness and oversized smoke module

- Problem: 29 UI modules duplicate QSettings isolation/setup, and
  `tests/ui/test_ui_smoke.py` contains unrelated feature contracts in about 1,900 lines.
- Evidence: repository-wide fixture and test-file inventory.
- Impact: setup drift, brittle maintenance, and poor failure localization.
- Recommended correction: first centralize behavior-identical fixtures, then split smoke
  tests by existing product contract without deleting or weakening assertions.
- Risk: hidden fixture-scope/order changes.
- Proposed slices: R4-A and R4-B.

### P1 — Windows offscreen validation debt

- Problem: three Qt/pyqtgraph UI nodes fail under the recorded Windows offscreen setup.
- Evidence: `test_floating_plots_geometry_survives_hide_show_and_restart` times out on
  restored geometry; histogram hover expects Code 20.5 but observes 21.5; Bayer line
  hover expects `Gr@1` but observes no sample. The first emits unsupported offscreen
  window-operation warnings; the two hover tests map coordinates without first showing
  and laying out the window.
- Impact: full-suite status is noisy and can conceal a real regression.
- Recommended correction: characterize product behavior versus offscreen artifacts and
  fix deterministic harness setup when possible. Do not skip/xfail, loosen thresholds,
  or change production behavior without evidence.
- Risk: platform/plugin differences may not be fully deterministic.
- Proposed slice: R5.

### P1 — durable semantic drift not caught mechanically

- Problem: ROADMAP/CURRENT_STATE/contracts still describe P5-F or older P5 slices as
  active even though PR #45 is merged; the docs checker validates paths/links, not
  cross-document phase semantics.
- Impact: a new worker starts from contradictory authority despite a passing docs check.
- Recommended correction: preserve the old P5 plan as completed history, split P5-G to
  deferred, activate R, and narrowly reconcile status lines. Later add bounded semantic
  guardrails where stable.
- Risk: broad documentation churn/history loss.
- Proposed slices: R0 now, R6 guardrails later.

### P2 — navigation and mechanical boundary clarity

- Problem: `MainWindow` and several domain trees are large, while import/layer rules are
  mostly prose rather than executable checks.
- Impact: navigation cost and implicit dependency risk.
- Recommended correction: add targeted import/ownership checks only for stable seams;
  split large files only when a later concrete change proves a cohesive extraction.
- Risk: file-move/format churn can exceed the structural value.
- Proposed slice: R6 or Deferred, based on evidence.

### P2 — phase-shaped top-level durable document names

- Problem: current Remote IQA contracts and characterization include P5-D/P5-E/P5-F
  phase names at the top of `docs/`, making current contract authority look like
  temporary execution history.
- Evidence: `P5D_VIEWER_INSPECTION.md`, `P5E_HISTORICAL_RESULTS.md`, and
  `P5F_INTEGRATION_CHARACTERIZATION.md` mix current behavior contracts with phase
  closure evidence. `REMOTE_IQA_V1_SPEC.md` and `REMOTE_IQA_V2_SPEC.md` also expose
  versions, but those names represent persisted schema compatibility and are necessary.
- Impact: current versus historical reading paths are less obvious, while removing
  schema versions would weaken compatibility authority.
- Recommended correction: in R6 evaluate a bounded phase-neutral contract/history
  structure, preserve explicit schema-v1/v2 identity, retain history, and move files
  only when link/history/deletion audit proves the navigation benefit.
- Risk: widespread link churn or accidental durable-history contraction.
- Proposed slice: R6; no file move in R0/R1.

### Deferred — speculative abstraction and policy changes

Generic generation frameworks, DI/service containers, broad source moves, MainWindow
rewrites, cache/preload/retry/concurrency changes, and production GPU/SMB/auth work are
not justified by current evidence and remain outside R.

## Implementation slices

Each slice is a separate small PR. Focused checks run during implementation; full gates
run before major integration points and R closeout. Every PR receives independent
read-only review of its latest whole head before merge.

### R0 — State reconciliation and executable program plan — Complete / PR #46

- Goal: make the P5-F merge, deferred P5-G gate, and active R program unambiguous.
- Expected areas: durable status documents and execution-plan directories only.
- Contract/non-goal: documentation-only; preserve all historical rationale and make no
  product, code, test, GitHub-setting, or external-environment claim.
- Focused validation: docs contract, docs unit test, stale-status search, Markdown link
  check, `git diff --check`, and base-to-head deletion/rename audit.
- Dependency: PR #45 merged.
- Merge criterion: all current-status authorities agree; no broken link or unexplained
  documentation contraction; independent latest-head PASS.

### R1 — Explicit application/IQA composition seam — Complete / PR #47

- Goal: make installer order and cross-controller dependencies visible and testable.
- Expected areas: `src/pixelscope/app/application.py`, IQA install/composition modules,
  focused composition
  tests, ARCHITECTURE/DECISIONS.
- Contract/non-goal: preserve every public action/signal/wrapper order, initialization,
  settings change, teardown, and UI behavior; no container/framework.
- Focused validation: application construction, IQA workspace/settings/open/Inspect/
  history/shutdown tests plus Ruff/mypy for changed modules.
- Dependency: R0.
- Merge criterion: explicit dependency graph with behavior-equivalent focused evidence
  and reviewer confirmation of wrapper/shutdown order.

### R2 — Worker and resource ownership injection — Complete / PR #48

- Goal: remove private post-construction pool rebinding and state ownership explicitly.
- Expected areas: P5-B/D/E controller constructors/installers, application Remote IQA
  pool composition, lifetime tests, architecture docs.
- Contract/non-goal: unchanged fixed max-two pools, job pool separation, cancel/clear/
  wait/shutdown ordering, lazy HTTP checkout, and stale callback rules.
- Focused validation: P5-F pool-binding/four-job shutdown, Result/Inspect/history stale
  intent tests, diagnostics, Ruff/mypy.
- Dependency: R1.
- Merge criterion: no controller temporarily owns the wrong pool; exact lifetime tests
  and independent race/ownership review PASS.

### R3-A — Obsolete Remote scaffold disposition — Complete / PR #49

- Goal: eliminate the misleading pre-P5 client only if repository/history evidence
  confirms it has no supported consumer.
- Expected areas: three legacy Remote modules, their isolated test, QUALITY/docs.
- Contract/non-goal: retain schema-v1 read-only result compatibility and every canonical
  P5 transport/result module; do not redesign APIs.
- Focused validation: import/reference inventory, all Remote unit/integration tests,
  package/import smoke, Ruff/mypy.
- Dependency: R0; may follow R2 to minimize composition overlap.
- Merge criterion: documented removal rationale, equivalent current-contract coverage,
  and compatibility reviewer PASS; otherwise record and retain it.

### R3-B — Session and legacy boundary clarification — Complete / PR #50

- Goal: make Session v1 authority and legacy Comparison Set adapter ownership explicit.
- Expected areas: comparison/session modules, facade/call sites, persistence tests/docs.
- Contract/non-goal: byte/field-compatible Session v1, unchanged transactional restore,
  Recent ownership, and legacy read behavior; no schema migration.
- Focused validation: Session/Comparison Set round-trip, missing/partial restore, Recent,
  UI integration, Ruff/mypy.
- Dependency: R1; independent of R3-A.
- Merge criterion: simpler boundary with identical persisted fixtures and reviewer PASS.

### R4-A — Common UI test fixtures — Complete / PR #51

- Goal: centralize behavior-identical QSettings/UI setup without changing test scope.
- Expected areas: `tests/ui/conftest.py` and affected UI tests.
- Contract/non-goal: no assertion deletion, scope broadening, global state leakage, or
  production change.
- Focused validation: representative settings-sensitive groups, then all UI tests once
  at slice completion.
- Dependency: R1/R2 stable composition.
- Merge criterion: fixture duplication reduced; isolation/order characterization PASS.

### R4-B — Smoke suite decomposition — Complete / PR #52

- Goal: split the oversized smoke module along existing product-contract boundaries.
- Expected areas: UI test modules/helpers only.
- Contract/non-goal: test-only moves with node coverage and assertions preserved; no
  cleanup by deletion.
- Focused validation: collected-node comparison, moved modules, all UI tests, diff audit.
- Dependency: R4-A.
- Merge criterion: same contract coverage and deterministic collection with clearer
  failure ownership; reviewer finds no lost regression.

### R5 — Windows/offscreen validation hardening — Complete / PR #53

- Goal: deterministically resolve or precisely constrain the three known failures.
- Expected areas: affected UI tests/harness, possibly test-only Qt helpers and QUALITY.
- Contract/non-goal: characterize first; no skip/xfail, arbitrary tolerance loosening,
  or production behavior change unless a separately justified product defect is found.
- Focused validation: repeated three-node runs under recorded platform/plugin/font
  conditions, related UI tests, base/current comparison where necessary.
- Dependency: R4 test harness stabilization.
- Merge criterion: deterministic PASS or exact documented environment constraint with
  no hidden failure and independent product-vs-harness review.

### R6 — Harness and architecture guardrails — review PASS / merge pending

- Goal: make stable ownership/status rules mechanically visible and evaluate a bounded
  phase-neutral current-contract versus historical-evidence document structure without
  building a new framework.
- Expected areas: docs checker, narrow import/architecture tests, QUALITY/index/harness
  notes, and Remote IQA durable-document paths only when the move value is proven.
- Contract/non-goal: enforce only durable proven rules; no speculative layer taxonomy or
  replacement of reviewer judgment. Preserve explicit schema-v1/v2 identity and all
  historical contracts; no mass move merely to reduce top-level file count.
- Focused validation: guardrail unit tests, docs contract, affected imports, Ruff/mypy.
- Dependency: R1–R5 reveal stable seams.
- Merge criterion: each rule has a concrete past failure/drift case and actionable output.

### R7 — Final integration validation and closeout

- Goal: verify all R slices together and leave one accurate repository state.
- Expected areas: validation evidence and narrow durable closeout updates.
- Contract/non-goal: no opportunistic feature/refactor work; P5-G remains deferred.
- Focused validation: `scripts/check_docs.py`, full pytest, Ruff check/format, mypy,
  pip check, `git diff --check`, and relevant manual Windows checks.
- Dependency: all accepted R slices.
- Merge criterion: exact results classified as PASS/regression/reproduced baseline/
  environment debt, independent latest-head review PASS, R archived Complete.

## Validation policy

For each slice run changed-file format/lint, directly affected tests, and the smallest
necessary regression set. Expand only for shared composition, worker infrastructure,
persistence/settings, or widely imported seam changes. Do not repeat full pytest at
every commit.

The final gate is:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Report only observed output and classify known failures explicitly. A reproduced
baseline or environment-dependent debt is never called full PASS.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| hidden wrapper-order change | composition/open/settings/shutdown tests and review | R1 exposes order before changing ownership |
| pool/lifetime race | queued-worker, stale-intent, shutdown tests | preserve policies; change injection only |
| compatibility/history loss | fixture/import/history and base-to-head diff audit | separate deletion/move PRs; retain archives |
| test weakening | node/assertion comparison and independent review | split fixtures/moves before any harness correction |
| offscreen artifact mistaken for product bug | repeated characterized runs | prefer test harness correction and document environment |
| documentation contraction | numstat/status/link checks | narrow edits from merged baseline; stop on unexplained deletions |

## Progress log

- 2026-08-24: audited `main@6634447fc3c48545a2482718dd3f444928806218`,
  PR #45 merged, no open PR, and a dirty tree containing owner untracked artifacts that
  are explicitly excluded from all R commits.
- 2026-08-24: reproduced the three known Windows offscreen nodes as three failures;
  no skip/xfail/tolerance or production change was made.
- 2026-08-24: started R0 on `codex/r0-refactoring-program`; archived the P5-through-P5-F
  plan and separated unobserved P5-G into a deferred plan.
- 2026-08-24: R0 focused validation observed `scripts/check_docs.py` PASS,
  `tests/unit/test_docs_contract.py` 1 passed, staged/unstaged `git diff --check` PASS,
  and no stale current-status pattern. The initial staged set contained 15 documentation
  files, including a 320-line retained P5 archive and an 83-line deferred P5-G plan; no
  source, test, or owner untracked artifact was staged.
- 2026-08-24: independent latest-head review requested one P2 correction: two audit
  references and the R1 expected area named the wrong composition-root path. Corrected
  them to `src/pixelscope/app/application.py` and aligned the execution-plan template
  with the new Deferred status; focused docs validation remained PASS.
- 2026-08-24: independent reviewer rechecked the full PR at
  `9d677aaf69fea1e9a3e42073a4e951081b960cfa`, confirmed the P2 finding closed, and
  reported PASS with no remaining actionable finding. Closure head `1e2d242e...` also
  passed latest-whole-head review; PR #46 merged at
  `main@a25b3ee1b08dc26b57776fd2a24c3b751f13ebfc`.
- 2026-08-24: started R1 from the R0 merge. Characterized the P5-C mapping → P5-D
  settings/Inspect → P5-E history/Provenance wrapper order and observed the focused
  pre-change baseline as 21 passed. Extracted `_compose_remote_iqa` as the smallest
  application-level seam, keeping private result-pool rebinding for R2. The first
  post-change focused run observed 22 passed; changed-file Ruff check and mypy passed,
  and Ruff format requested then applied one mechanical `application.py` reflow.
- 2026-08-24: owner asked whether phase/version-named top-level documents should remain.
  Recorded R6 evaluation of phase-neutral current contracts versus historical evidence;
  schema v1/v2 remains explicit persisted-contract identity and no move is mixed into
  R0/R1.
- 2026-08-24: R1 expanded validation observed 206 passed, 1 skipped, and 243 deselected
  for the P5/Remote-IQA unit selection, followed by 161 passed and 304 deselected for
  the P4/P5 UI selection. The skip is the existing Windows directory-symlink privilege
  constraint. No full-suite PASS is claimed; independent latest-whole-head review is
  pending.
- 2026-08-24: independent review of `d917e9ac...` found the implementation order,
  wrapper chains, pool policies, tests, and validation scope sound, and requested one
  P2 documentation correction: PRODUCT_SPEC and UI status still named the P5-F merge
  as the current baseline. Updated both current-status authorities to the R0 merge
  `a25b3ee1...` while retaining historical P5-F identities. Although the reviewer found
  the transport-construction/pool-bind reordering unobservable, R1 also restored the
  original relative order because no change was required.
- 2026-08-24: independent reviewer rechecked latest whole head
  `33ebd9cf3720bf18e5eac7d22765ca08d8e45bcb`, confirmed the P2 finding and exact-order
  remediation closed, independently observed 32 focused tests plus static/docs/diff
  gates passing, and reported PASS with no remaining actionable finding. Closure head
  `1e222d1dfe3cd4a85178ddc98c7d3cd780b1c99c` also passed whole-head review; PR #47
  merged at `main@808f1e6bccd67e649be71b03798a1a1f407628f8`.
- 2026-08-24: started R2 from the R1 merge. The pre-change ownership/lifecycle selection
  observed 42 passed. Production now creates the existing Remote IQA result/file pool
  before `MainWindow`, injects it into P5-B construction, and forwards the same pool to
  P5-D/P5-E installers. Private post-install `_pool` assignments were removed; pool
  counts, worker operations, HTTP lifetime, stale guards, and composition order were
  not changed. Initial composition/ownership tests observed 6 passed, changed-source
  mypy passed, and the full focused selection observed 42 passed after implementation.
- 2026-08-24: expanded R2 validation observed 212 passed, 1 skipped, and 238 deselected
  for P5/Remote-IQA unit coverage plus 62 passed and 403 deselected for P5 UI coverage.
  The skip is the existing Windows directory-symlink privilege constraint. Changed-file
  Ruff check/format and five-module mypy passed; docs checker, docs contract test, and
  diff check passed. No full-suite PASS is claimed; independent latest-whole-head review
  remains the merge gate.
- 2026-08-24: independent review of `5533fc4f527e30a559ad7e5b2b45474c3386ebdc`
  requested two P1 lifecycle corrections and one P2 PR-attribution correction. R2 now
  initializes the analysis pool before the Remote IQA pool to preserve the existing Qt
  shutdown-hook clear/wait order, and P5-D/P5-E idempotent installers reject a different
  explicit pool while retaining same-pool idempotency. Focused regressions cover the
  fresh registration/clear/wait sequence and both installer outcomes; the remediated
  focused selection observed 44 passed and changed-file Ruff/format/mypy passed. The PR
  body records the actual owner-authenticated Git/GitHub attribution and non-rewrite of
  human commits. Latest-whole-head re-review remains pending.
- 2026-08-24: independent reviewer rechecked latest whole head
  `a1c18d0ccb2820b9cba163df18c3f725495a6c64`, confirmed both P1 lifecycle findings
  and the P2 attribution finding closed, independently observed 40 focused tests plus
  changed-file Ruff/format/mypy, docs checker/contract, and base-to-head diff gates
  passing, and reported PASS with no remaining actionable finding. Latest implementer
  broad reruns observed 212 passed, 1 skipped, and 239 deselected for P5/Remote-IQA
  units plus 62 passed and 403 deselected for P5 UI. R2 merge is pending.
- 2026-08-24: R2 closure head `93a514ad722e7662a396a1f19f142499722490ad`
  passed final docs-only whole-head review, and PR #48 merged at
  `main@7c0d326fd2a8ff767ac916d29af1c7d5ee44abd6`.
- 2026-08-24: started R3-A from the R2 merge. All three pre-P5 Remote modules and their
  sole test originated together in initial release `262cd5b` and had no later history,
  package export, production import, or consumer outside that isolated test. The same
  historical `/v1/jobs` sketch also remained in `server/api_contract.md`; it is retained
  with an explicit historical/unsupported label and canonical-contract link. Pre-change
  scaffold plus canonical Remote coverage observed 123 passed and import smoke PASS.
  After removing only the three dead modules and self-only test, canonical focused
  coverage observed 121 passed, canonical import/legacy absence smoke passed, Remote
  Ruff passed, and mypy reported no issues in 29 source files. Schema-v1 Result and
  canonical `/v1/iqa/jobs` contracts remain unchanged.
- 2026-08-24: expanded latest-head Remote/IQA unit selection observed 212 passed,
  1 skipped, and 237 deselected. The skip is the existing Windows directory-symlink
  privilege constraint. Ruff check and format passed for all Remote source plus unit
  tests, mypy passed all 29 remaining Remote source files, pip check reported no broken
  requirements, docs checker/contract passed, and diff check passed. No full-suite PASS
  is claimed; independent compatibility review remains the merge gate.
- 2026-08-24: independent compatibility review of latest whole head
  `94f56e1225be109f53731d3da3ab2a20e485602a` confirmed the four removed files have
  no post-initial history, production/script/test/export consumer, Git tag, or GitHub
  Release commitment. The reviewer verified canonical schema-v1 and `/v1/iqa/jobs`
  sources remain byte-identical, package discovery finds 7 packages and 28 supported
  Remote modules with the legacy modules absent, independently reproduced the 212/1/237
  unit result plus import/package/static/docs/diff gates, and reported PASS. The only
  residual compatibility risk is an undocumented repository-external deep importer;
  R3-A merge is pending.
- 2026-08-24: R3-A closure head `da7f066aeb4975c13cb5815c274a10ea112642aa`
  passed final docs/body review, and PR #49 merged at
  `main@a97bfb68e1113afea4ea905d7ccbbb1f67a9bde1`.
- 2026-08-24: started R3-B from the R3-A merge. Audit confirmed Session v1 domain/write
  authority is already centralized in `Session` and `ComparisonSetRepository`; the
  maintainability issue was UI naming around the shared base, production transactional
  subclass, and legacy selected-count facade. The pre-change persistence/Recent/UI
  selection observed 72 passed. R3-B adds the explicit `SessionControllerBase` role,
  names the legacy facade, makes Recent depend on the production Session controller,
  and locks production/facade ownership in a focused test. It does not consolidate the
  divergent restore algorithms or change persisted/return behavior. Post-change focused
  selection observed 73 passed; changed-file Ruff and three-module mypy passed.
- 2026-08-24: expanded latest-head P4/persistence selection observed 101 passed and
  390 deselected. Changed-file Ruff check/format and three-module mypy passed, pip check
  reported no broken requirements, docs checker/contract passed, and diff check passed.
  No full-suite PASS is claimed; independent persisted-data/compatibility review remains
  the merge gate.
- 2026-08-24: independent review of `64a0fdbc44dd1266ba7e3519ebfca4a35a67bcf3`
  found one P1 compatibility regression: narrowing Recent to the production subclass
  rejected the retained `install_comparison_set` + `install_recent_entries` composition.
  Recent now checks `SessionControllerBase`, production composition remains locked to
  the transactional subclass, and a focused regression covers successful legacy
  installer/Recent composition. Persisted and facade behavior remain unchanged;
  latest-head re-review is pending.
- 2026-08-24: independent reviewer rechecked latest whole head
  `734b633af4a89555cda19ccfee7a808fbed72279`, confirmed the P1 closed, verified both
  legacy and production compositions plus both import orders, and confirmed Session
  domain/repository byte identity and facade selected-count adaptation remain unchanged.
  The reviewer observed 79 focused tests plus Ruff/format/mypy/docs/diff gates passing
  and reported PASS with no remaining actionable finding. R3-B merge is pending.
- 2026-08-24: R3-B closure head `27227271defd61f411214aee2594324f3d5da849`
  passed final docs-only review, and PR #50 merged at
  `main@6e98baea425f3dfbfacc1140370a77e889673a76`.
- 2026-08-24: started R4-A from the R3-B merge. The audit classified 28 module-level
  autouse QSettings fixtures into three behavior-distinct groups: clear under
  `tmp_path`, clear plus explicit `sync()`, and P5-E clear under
  `tmp_path / "settings"`. R4-A centralizes those exact operations as opt-in fixtures
  in `tests/ui/conftest.py`; modules opt in with `pytest.mark.usefixtures`, so the
  fixture does not broaden to unrelated UI tests. Inline mid-test clears and the
  P5-D stale-inspection setup remain untouched because their timing or scope differs.
  A representative pre-change run observed 103 passed and the two known pyqtgraph
  hover failures; the same selection after migration observed the identical result.
  The full post-change UI run observed 464 passed and the exact three carried Windows
  offscreen failures in 273.54 seconds. Repository Ruff check/format and diff check
  passed. Independent latest-whole-head review remains the merge gate.
- 2026-08-24: independent review of latest whole head
  `d1244c294ddd245c9142aaae81e4c1d8f5b6ce47` confirmed the 28 removed module
  fixtures map one-to-one to 28 opt-in modules; no-sync, explicit-sync, temporary-root,
  and P5-E settings-subdirectory behavior remain distinct. Node/assertion/
  parametrization/skip/xfail coverage is unchanged, and the timing-distinct P5-D setup
  remains local. The reviewer observed 467 collected nodes, then 464 passed plus the
  exact three carried offscreen failures in 270.75 seconds; Ruff, format, pip, docs,
  docs-contract, and diff gates passed. One P2 PR-provenance finding requested the
  actual Git and GitHub account identities. The PR body now records Git author and
  committer `mc.kang <delphykmc@gmail.com>`, the ChatGPT co-author trailer on every
  R4-A commit, GitHub CLI account `delphykmc`, and no human-commit rewrite. Body-only
  re-review confirmed the finding closed and reported PASS. Full repository pytest,
  mypy, interactive Windows UI, packaging, and real GPU/SMB remain unverified and are
  not claimed.
- 2026-08-24: R4-A closure head `53503c53501d2d63be11a7c30a341a9c237a3103`
  passed final docs-only review, and PR #51 merged at
  `main@336a27e5e10e3d5e8d83bc18046bec837daa5b96`.
- 2026-08-24: started R4-B from the R4-A merge. The 39 tests in the approximately
  1,900-line `test_ui_smoke.py` were moved without renaming into six phase-neutral
  contract modules: workspace, Difference, plots/statistics, input/navigation, viewer
  interaction, and RAW input. A base-to-head AST comparison confirmed all 39 function
  bodies are identical. Collection remained 39 for the moved group and 467 for all UI
  tests. The focused pre-change result was 37 passed plus the two carried pyqtgraph
  hover failures; the post-change result was identical. The full UI run observed
  464 passed plus the exact three carried Windows offscreen failures in 280.06 seconds.
  Ruff check/format and diff check passed. No production source, assertion,
  parametrization, skip, or xfail changed. Independent latest-whole-head review remains
  the merge gate.
- 2026-08-24: independent review of latest whole head
  `fe252eacae2d3846f3f036ba0c389db9ca073ae0` found no actionable issue. The
  reviewer confirmed a one-to-one 39-function AST mapping with no missing, duplicate,
  or changed body; preserved fixtures/assertions/parametrization/skip/xfail; cohesive
  six-module boundaries; and no QSettings/order or durable-history regression.
  Independent validation observed 39 collected with 37 passed plus two known failures,
  and all UI observed 467 collected with 464 passed plus the exact three known failures
  in 274.33 seconds. Ruff, format, pip, docs, docs-contract, and diff gates passed.
  Full repository pytest, mypy, interactive UI, packaging, and GPU/SMB remain
  unverified and are not claimed. Reviewer reported PASS.
- 2026-08-24: R4-B closure head `e370f5a7a1efbdf11bd7eec3fc738f8e87b49a2d`
  passed final docs-only review, and PR #52 merged at
  `main@39b8c77fbf8a497d2787f33b8e119d2ddbed9604`.
- 2026-08-24: started R5 from the R4-B merge. Characterization confirmed the histogram
  test targeted exact bin edge 21 while production intentionally uses right-side bin
  selection; using interior point 20.5 preserves the expected Code 20.5 contract. The
  Bayer hover test mapped a hidden line-profile plot; explicitly showing the window and
  target tab makes its scene transform valid. The offscreen plugin cannot reproduce
  floating-window placement across restart, so the test now always verifies persisted
  QByteArray restore authority and retains actual geometry equality on window-manager
  platforms; same-process hide/show geometry remains asserted everywhere. No production
  source, expected numerical value, tolerance, skip, or xfail changed. The three debt
  nodes passed five consecutive runs (15/15), related modules passed 19 tests, and the
  full Windows offscreen UI suite passed all 467 tests in 268.42 seconds. Ruff and diff
  gates passed. Independent latest-whole-head review remains the merge gate.
- 2026-08-24: independent review of latest whole head
  `0a13040aec9929a5f272831ba8c7c275a265b9d1` confirmed the interior histogram point,
  visible-plot preconditions, and capability-specific geometry assertion preserve the
  intended contracts without hiding a product defect. Persisted geometry, restored
  floating state, and same-process geometry remain unconditional; restart coordinates
  remain asserted on non-offscreen platforms. The reviewer observed 15/15 repeated
  debt-node passes, 19 related passes, and all 467 UI tests passing in 272.57 seconds;
  Ruff, format, pip, docs, docs-contract, and diff gates passed. No production source,
  expectation, tolerance, skip, xfail, dependency, or packaging change was found.
  Actual restart placement on window-manager platforms, full repository pytest, mypy,
  interactive UI, packaging, and external GPU/SMB remain unverified and are not claimed.
  Reviewer reported PASS.
- 2026-08-24: R5 closure head `be73bf4802cc215ce262357bafb50c65d013a224`
  passed final docs-only review, and PR #53 merged at
  `main@45e718abe28ab600edab41cf04a998029f6fc5f7`.
- 2026-08-24: started R6 from the R5 merge. The stable existing rule that numerical
  `core/` and `io/` remain independent of PySide6/pyqtgraph now has an AST-based
  repository guardrail with actionable file/line diagnostics; its repository and
  negative-diagnostic tests observed 2 passed. Document-structure evaluation retained
  explicit schema-v1/v2 filenames as compatibility authority and retained phase-named
  P5-D/P5-E/P5-F root documents because they preserve historical scope and moving them
  would churn roughly twenty durable links. `docs/index.md` now makes their current
  contract versus closure-evidence roles explicit. No production source or document was
  moved. Independent latest-whole-head review remains the merge gate.
- 2026-08-24: independent review of R6 found one P2 semantic drift: QUALITY still
  described R5 review as pending after PR #53 merged. QUALITY now records the actual
  independent PASS and merge SHA. Latest whole-head re-review at
  `d1d277c445e76599608fd4386f76282e7de61d65` confirmed the finding closed, the
  guardrail catches direct/submodule/from imports for both forbidden frameworks, and
  the bounded document-retention decision preserves authority and history. The reviewer
  observed 451 unit passes with one environment-dependent symlink skip, focused 3
  passes, Ruff/format/pip/docs/diff PASS, and reported PASS. Full repository pytest,
  mypy, interactive UI, packaging, dynamic imports, and `.pyi` imports remain
  unverified and are not claimed.

## Completion summary

Active. Fill this section at R7 closeout with delivered behavior, changed files, exact
validation, manual checks, constraints, deferred work, and agent attribution.
