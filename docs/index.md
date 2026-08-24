# PixelScope documentation map

The repository is the system of record. `AGENTS.md` is the entry map; durable
knowledge belongs in focused documents under `docs/`.

## Read by task

| Task type | Read first | Update when |
|---|---|---|
| Any implementation task | `CURRENT_STATE.md` | Completed scope, verified backlog, or assumptions change |
| User-visible workflow | `PRODUCT_SPEC.md`, `USER_GUIDE.md`, relevant `ui/` note | Behavior, terminology, shortcut, or workflow changes |
| Session persistence / Recent entry UX | `SESSION_CONTRACT.md` | Session schema, restore transaction, legacy compatibility, Recent ownership, or PR #32/#33 integration changes |
| Remote IQA result/schema/submission work | `REMOTE_IQA_CONTRACT.md`, `REMOTE_IQA_V2_SPEC.md`, current/deferred execution plan as applicable | Measurement/comparison ownership, storage/request/job identity, result schema, summaries/grids, loading boundaries, or P5 sequencing change |
| Core/UI/worker/cache/lifecycle | `ARCHITECTURE.md`, `DECISIONS.md` | Ownership, boundary, invariant, or data flow changes |
| Multi-step feature/refactor | `CURRENT_STATE.md`, `ROADMAP.md`, active execution plan | Scope, milestones, risks, or follow-up work changes |
| RAW decoding/profile work | `ARCHITECTURE.md`, `QUALITY.md`, RAW tests and fixtures | Storage schema, validation, decoder, or Bayer behavior changes |
| Branding/application identity | `BRANDING.md`, `PACKAGING_CONSTRAINTS.md`, `DECISIONS.md` | Product mark, canonical assets, resource loading, or release-icon use changes |
| Packaging/dependency | `PACKAGING_CONSTRAINTS.md`, `DECISIONS.md` | Runtime, dependency, installer, or resource-loading constraints change |
| Test/validation | `QUALITY.md` | Required checks, fixtures, smoke paths, or evidence standards change |
| Agent-assisted workflow | `AGENT_HARNESS_NOTES.md` | A durable harness lesson or guardrail changes |

## Document roles

- `CURRENT_STATE.md`: dated implementation baseline, corrected assumptions, and
  prioritized backlog.
- `PRODUCT_SPEC.md`: stable user-visible contracts.
- `ARCHITECTURE.md`: current component boundaries, state ownership, data flow,
  and lifecycle invariants; planned components are explicitly marked.
- `DECISIONS.md`: accepted engineering decisions and pending owner decisions.
- `ROADMAP.md`: phase-level delivered and future scope.
- `REMOTE_IQA_CONTRACT.md`: broad P5 Remote IQA product/architecture/transport
  boundary, including P5-C storage/submission/jobs/PARTIAL ownership.
- `REMOTE_IQA_V2_SPEC.md`: current executable P5 numerical/result-schema authority,
  including COMPLETE and P5-C PARTIAL schema-v2 rules.
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
- `PACKAGING_CONSTRAINTS.md`: deployment environment and fixed packaging rules.
- `USER_GUIDE.md`: end-user workflows, including Remote IQA configuration,
  submission, Jobs, explicit Open Result, and result exploration.
- `QUALITY.md`: change-to-check matrix and completion evidence.
- `AGENT_HARNESS_NOTES.md`: reusable harness lessons for humans and agents.
- `ui/implementation_status.md`: detailed UI iteration audit.
- `ui/p1b_plots_plan.md`: completed and remaining P1-B plot work.
- [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md): required current
  pointer; no repository implementation program is active after R closeout.
- [`exec-plans/completed/repository-refactoring-validation-hardening.md`](exec-plans/completed/repository-refactoring-validation-hardening.md):
  retained R0–R7 plan, findings, validation, review, and closeout evidence.
- [`exec-plans/deferred/p5g-external-gpu-smb-validation.md`](exec-plans/deferred/p5g-external-gpu-smb-validation.md):
  authoritative unobserved external GPU/SMB validation and final P5 closeout gate.
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
6. Rewrite or remove stale guidance instead of appending contradictory notes.
7. Keep temporary compatibility paths explicitly marked with an owner and
   removal condition.
8. Use an execution plan when work crosses components, has unresolved design
   choices, or is likely to span multiple commits or sessions.
9. Move substantial completed plans to `exec-plans/completed/`, keep unavailable but
   still-authoritative work in `exec-plans/deferred/`, and keep the required current
   plan at `exec-plans/active/next-phase.md`.
10. Retain explicit schema-v1/v2 filenames as compatibility authority. Use
    phase-neutral filenames for current durable contracts at the docs root; preserve
    phase identity inside those documents and in completed execution history.

## Mechanical documentation check

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
```

The check verifies required harness files and local Markdown links. Pytest also
runs the same contract through `tests/unit/test_docs_contract.py`.
