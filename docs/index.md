# PixelScope documentation map

The repository is the system of record. `AGENTS.md` is the entry map; durable
knowledge belongs in focused documents under `docs/`.

## Read by task

| Task type | Read first | Update when |
|---|---|---|
| Any implementation task | `CURRENT_STATE.md` | Completed scope, verified backlog, or assumptions change |
| User-visible workflow | `PRODUCT_SPEC.md`, `USER_GUIDE.md`, relevant `user-guide/` topic and `ui/` note | Behavior, terminology, shortcut, format semantics, or workflow changes |
| Session persistence / Recent entry UX | `SESSION_CONTRACT.md` | Session schema, restore transaction, legacy compatibility, Recent ownership, or PR #32/#33 integration changes |
| Historical P5 Remote-IQA archaeology | `REMOTE_IQA_CONTRACT.md`, `REMOTE_IQA_V2_SPEC.md`, and completed/deferred P5 records | Historical transport/storage/result-schema behavior or migration archaeology; these documents are not current MAIN runtime APIs |
| Base / IQA Reference / Enterprise ownership or SUB handoff | `IQA_HANDOFF.md`, `IQA_OWNERSHIP.md`, `IQA_DOWNSTREAM_CONTRACT.md`, `iqa_reference/README.md`, then relevant `ARCHITECTURE.md` / `DECISIONS.md` sections | Repository/source ownership, peer-extension dependency direction, public provider/host boundary, reference behavior, downstream conformance, synthetic-vs-confidential data rules, lifecycle compatibility, or exact-MAIN-SHA sync policy |
| Core/UI/worker/cache/lifecycle | `ARCHITECTURE.md`, `DECISIONS.md` | Ownership, boundary, invariant, or data flow changes |
| Multi-step feature/refactor | `CURRENT_STATE.md`, `ROADMAP.md`, active execution plan | Scope, milestones, risks, or follow-up work changes |
| RAW decoding/profile work | `ARCHITECTURE.md`, `QUALITY.md`, RAW tests and fixtures, `user-guide/formats/raw.md` | Storage schema, validation, decoder, Bayer behavior, or user-facing RAW interpretation changes |
| Branding/application identity | `BRANDING.md`, `PACKAGING_CONSTRAINTS.md`, `DECISIONS.md` | Product mark, canonical assets, resource loading, or release-icon use changes |
| Packaging/dependency | `PACKAGING_CONSTRAINTS.md`, `BUILD_AND_RELEASE.md`, `DECISIONS.md` | Runtime, dependency, installer, release metadata, publication, or resource-loading constraints change |
| Owner-local Beta build/release | `BUILD_AND_RELEASE.md`, `PACKAGING_CONSTRAINTS.md` | Human build flow, candidate handoff, validation sequence, or publication procedure changes |
| Test/validation | `QUALITY.md` | Required checks, fixtures, smoke paths, or evidence standards change |
| Agent-assisted workflow | `AGENT_HARNESS_NOTES.md` | A durable harness lesson or guardrail changes |

## Document roles

- `CURRENT_STATE.md`: dated implementation baseline, corrected assumptions, and
  prioritized backlog.
- `PRODUCT_SPEC.md`: stable user-visible contracts.
- `ARCHITECTURE.md`: current component boundaries, state ownership, data flow,
  and lifecycle invariants; planned components are explicitly marked.
- `IQA_HANDOFF.md`: Issue #121 Slice 8 operational handoff authority for stable host/
  public IQA contracts, lifecycle/concurrency/configuration rules, conformance,
  exact-MAIN-SHA sync, packaging shapes, and downstream patch policy.
- `IQA_OWNERSHIP.md`: authoritative post-Checkpoint-C MAIN/SUB source-ownership and
  dependency contract for PixelScope Base/Core, MAIN Reference/Mock IQA, and SUB
  Enterprise IQA peer extensions, including reserved paths and the
  no-confidential-runtime rule.
- `IQA_BOUNDARY_CHARACTERIZATION.md`: Issue #121 Slice 1 inventory of current concrete
  Base/IQA coupling, production install/shutdown order, settings ownership, IQA test
  classes, and the minimum public provider/result semantics that Slice 2 preserves.
- `IQA_DOWNSTREAM_CONTRACT.md`: revised downstream consumer contract preserving the
  useful Slice 5 public-port/concurrency/pinning rules while making the SUB Enterprise
  extension a peer consumer of MAIN host/contracts. Real Enterprise smoke is a
  downstream release responsibility, not a prerequisite for MAIN Slice 6-8.
- `iqa_reference/README.md`: Revised Slice 6 physical-extraction inventory, generic
  host additions, reference/mock composition/behavior, immutable baseline snapshot,
  dependency rules, and Slice 7 cleanup boundary.
- [`exec-plans/completed/iqa-downstream-transfer-contract.md`](exec-plans/completed/iqa-downstream-transfer-contract.md):
  retained Slice 5 draft/review/reconciliation record; completion is documentation-
  contract completion, not production Enterprise qualification.
- `DECISIONS.md`: accepted engineering decisions and pending owner decisions.
- `ROADMAP.md`: phase-level delivered and future scope.
- `REMOTE_IQA_CONTRACT.md`: historical P5 Remote-IQA product/architecture/transport
  boundary retained for implementation archaeology.
- `REMOTE_IQA_V2_SPEC.md`: historical P5 numerical/result-schema authority retained
  for migration/reference archaeology; the runtime implementation is retired from MAIN.
- `REMOTE_IQA_V1_SPEC.md`: historical merged P5-A/schema-v1 executable/read-only
  compatibility contract; it is not the current writer/numerical target.
- `REMOTE_IQA_VIEWER_INSPECTION.md`: additive native-Inspect contract and retained
  P5-D closure evidence.
- `REMOTE_IQA_HISTORICAL_RESULTS.md`: historical-Result contract and retained P5-E
  closure evidence.
- `REMOTE_IQA_INTEGRATION_CHARACTERIZATION.md`: retained repository-side integration and
  performance characterization; it does not claim the deferred external P5-G gate.
- `SESSION_CONTRACT.md`: authoritative P4-C Session v1 persistence, restore,
  legacy Comparison Set compatibility, typed Recent, and PR #32/#33 integration
  contract.
- `BRANDING.md`: canonical application identity, asset roles, visual constraints,
  supported icon sizes, and release-tool consumption rules.
- `PACKAGING_CONSTRAINTS.md`: deployment environment, fixed packaging rules, release
  candidate/provenance lineage, and publication-boundary constraints.
- `BUILD_AND_RELEASE.md`: concise owner-local Windows Beta build, candidate handoff,
  provider-neutral publication staging, and revalidation runbook; normative rules remain
  in `PACKAGING_CONSTRAINTS.md`.
- `USER_GUIDE.md`: stable repository entry point for the end-user guide and its build
  instructions; canonical task/feature/format/reference content lives under
  `user-guide/` and is built by `mkdocs.yml`.
- `USER_GUIDE_PRE_MKDOCS.md`: historical snapshot of the pre-MkDocs monolithic guide;
  retained for history, not current user-facing authority.
- `USER_GUIDE_FOLLOW_UP.md`: scoped Help/packaging/deployment/agent-interface follow-up
  work that is intentionally outside the User Guide foundation.
- `user-guide/`: canonical end-user Markdown source for the searchable/offline site;
  avoid developer phase names and internal implementation terminology here.
- `QUALITY.md`: change-to-check matrix and completion evidence.
- `AGENT_HARNESS_NOTES.md`: reusable harness lessons for humans and agents.
- `ui/implementation_status.md`: detailed UI iteration audit.
- `ui/beta_workspace_hardening.md`: Beta layout/floating-window contract, root causes,
  focused regression coverage, and Windows/multi-monitor manual checklist.
- `ui/p1b_plots_plan.md`: completed and remaining P1-B plot work.
- [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md): required current
  pointer; P7-D Stage 1 Release Metadata & Manual Publication Foundation is active.
  Historical P5-G/P6 Enterprise integration no longer gates MAIN after Issue #121.
- [`exec-plans/active/p7-release-foundation.md`](exec-plans/active/p7-release-foundation.md):
  active P7 foundation sequence, including the P7-D Stage 1/Stage 2 boundary.
- [`exec-plans/active/p7-release-publication-audit.md`](exec-plans/active/p7-release-publication-audit.md):
  current P7-D Stage 1 publication metadata, provenance, tag/manual-publication, and
  provider-neutral update-discovery separation contract.
- [`exec-plans/active/beta-ui-owner-spacing-followup.md`](exec-plans/active/beta-ui-owner-spacing-followup.md):
  bounded diagnosis, correction, validation, and review record for the final PR #68
  owner-observed RAW and Plots spacing regressions.
- [`exec-plans/completed/beta-ui-hardening-dpi-followup.md`](exec-plans/completed/beta-ui-hardening-dpi-followup.md):
  retained integration, validation, and exact-head review record for the PR #69 DPI
  command-row experiment incorporated selectively into draft PR #68.
- [`exec-plans/completed/repository-refactoring-validation-hardening.md`](exec-plans/completed/repository-refactoring-validation-hardening.md):
  retained R0–R7 plan, findings, validation, review, and closeout evidence.
- [`exec-plans/completed/beta-ui-hardening-pass2.md`](exec-plans/completed/beta-ui-hardening-pass2.md):
  retained Beta UI Hardening Pass 2 audit, implementation, owner-finding fix loops,
  validation, and exact-head review evidence for draft PR #68.
- [`exec-plans/deferred/p5g-external-gpu-smb-validation.md`](exec-plans/deferred/p5g-external-gpu-smb-validation.md):
  retained historical external-validation plan; real Enterprise qualification is now
  downstream SUB work and is not a MAIN closeout gate.
- [`exec-plans/completed/p5-remote-iqa-platform-through-p5f.md`](exec-plans/completed/p5-remote-iqa-platform-through-p5f.md):
  retained P5 program rationale and repository-side closure through P5-F / PR #45.
- [`exec-plans/completed/p5-schema-v2-revision.md`](exec-plans/completed/p5-schema-v2-revision.md):
  retained rationale/closure record for the completed P5-A2 schema-v2 interruption.
- [`exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md): retained P1 workspace-polish rationale and completion evidence.
- `exec-plans/completed/`: retained plans whose rationale remains useful.
- `exec-plans/deferred/`: executable future plans blocked by explicit environment or
  authority prerequisites; deferred status is not PASS.
- `exec-plans/TEMPLATE.md`: standard long-work format.

## Maintenance rules

1. Keep each fact in one authoritative document and link to it elsewhere.
2. State what is true now; do not leave completed work described as future work.
3. Prefer focused documents over a growing monolithic instruction file.
4. Record stable invariants, concrete paths, commands, states, and failure
   conditions rather than chat history.
5. Update documentation in the same PR as behavior or architecture changes.
6. For user-visible behavior, review User Guide impact in the same PR and update the
   owning `user-guide/` topic rather than duplicating prose in `USER_GUIDE.md`.
7. Rewrite or remove stale guidance instead of appending contradictory notes.
8. Keep temporary compatibility paths explicitly marked with an owner and
   removal condition.
9. Use an execution plan when work crosses components, has unresolved design
   choices, or is likely to span multiple commits or sessions.
10. Move substantial completed plans to `exec-plans/completed/`, keep unavailable but
   still-authoritative work in `exec-plans/deferred/`, and keep the required current
   plan at `exec-plans/active/next-phase.md`.
11. Retain explicit schema-v1/v2 filenames as compatibility authority. Use
    phase-neutral filenames for current durable contracts at the docs root; preserve
    phase identity inside those documents and in completed execution history.

## Mechanical documentation check

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
```

The check verifies required harness/User Guide entry points, canonical User Guide
navigation coverage, and local Markdown links. Pytest also runs the same contract
through `tests/unit/test_docs_contract.py`.

When the User Guide source or platform changes, also run:

```powershell
.\.venv\Scripts\python.exe -m mkdocs build --strict
```
