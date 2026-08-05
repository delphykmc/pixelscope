# PixelScope documentation map

This directory is the repository system of record. `AGENTS.md` is only the entry map; durable knowledge belongs here.

## Read by task

| Task type | Read first | Update when |
|---|---|---|
| User-visible behavior or workflow | `PRODUCT_SPEC.md`, relevant `ui/` note, `USER_GUIDE.md` | Behavior, terminology, shortcuts, or workflow changes |
| Core, UI, worker, cache, or lifecycle change | `ARCHITECTURE.md`, `DECISIONS.md` | Boundaries, ownership, invariants, or data flow changes |
| Multi-step feature or refactor | `ROADMAP.md`, `exec-plans/TEMPLATE.md` | Scope, milestones, risks, or follow-up work changes |
| Packaging or dependency change | `PACKAGING_CONSTRAINTS.md`, `DECISIONS.md` | Runtime, dependency, installer, or resource-loading constraints change |
| Test or validation change | `QUALITY.md` | Required checks, fixtures, smoke tests, or evidence standards change |
| Agent-assisted development practice | `AGENT_HARNESS_NOTES.md` | The workflow produces a durable new lesson |

## Document roles

- `PRODUCT_SPEC.md`: stable product behavior and user-facing contracts.
- `ARCHITECTURE.md`: current component boundaries, state ownership, data flow, and lifecycle invariants.
- `DECISIONS.md`: short record of accepted decisions and constraints. Do not use as a chronological work log.
- `ROADMAP.md`: phase-level scope and deferred capabilities.
- `PACKAGING_CONSTRAINTS.md`: deployment environment and fixed packaging requirements.
- `USER_GUIDE.md`: instructions for end users.
- `QUALITY.md`: validation matrix and completion evidence.
- `AGENT_HARNESS_NOTES.md`: reusable lessons for humans and coding agents.
- `exec-plans/active/`: plans for work currently in progress.
- `exec-plans/completed/`: retained plans for substantial completed work when the rationale remains useful.
- `exec-plans/TEMPLATE.md`: standard format for long-running work.

## Maintenance rules

1. Keep each fact in one authoritative document and link to it elsewhere.
2. Prefer small focused documents over one large manual.
3. Record stable invariants, not transient chat context.
4. Include concrete file paths, commands, states, and failure conditions where useful.
5. Update documentation in the same PR as the behavior or architecture change.
6. Remove or rewrite stale guidance instead of appending contradictory notes.
7. A document should state what is true now. Historical reasoning belongs in `DECISIONS.md` or a completed execution plan.

## Agent navigation rule

Before editing code, identify the task category in the table above and read only the relevant documents. If the task crosses two or more architecture areas, has unresolved design choices, or is expected to span multiple commits, create an execution plan before implementation.
