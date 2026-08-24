# Execution plan: <title>

Status: Draft | Active | Blocked | Deferred | Complete
Owner: <human or agent>  
Branch/PR: <link or name>  
Last updated: YYYY-MM-DD

## Goal

Describe the user-visible or engineering outcome in one paragraph. State how completion will be observed.

## Scope

### In scope

- <explicit deliverable>

### Out of scope

- <deliberately deferred item>

## Current state

Summarize the relevant implementation and cite concrete files, classes, functions, tests, and documents. Do not rely on chat history.

## Invariants and constraints

- <behavior that must remain true>
- <runtime, compatibility, performance, or packaging constraint>

## Proposed design

Explain state ownership, data flow, API changes, failure handling, thread boundaries, and compatibility impact. Record alternatives only when they affect the chosen design.

## Implementation slices

1. **Slice name**
   - Files/components:
   - Observable result:
   - Tests:

Keep each slice independently reviewable where possible.

## Validation plan

- Targeted automated tests:
- Full checks from `docs/QUALITY.md`:
- Manual Windows checks:
- Performance or memory checks:

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| <risk> | <test or signal> | <design or rollback> |

## Progress log

- YYYY-MM-DD: <decision, completed slice, discovered constraint, or blocker>

Update this section during work. Keep it factual and concise.

## Completion summary

Fill in at completion:

- Delivered behavior:
- Changed files:
- Validation results:
- Remaining limitations:
- Follow-up issues:
- Durable docs updated:

Move substantial completed plans to `docs/exec-plans/completed/` when their rationale
remains useful. Move plans whose explicit environment or authority prerequisite is
unavailable to `docs/exec-plans/deferred/`; Deferred is not PASS. Delete trivial or
obsolete plans rather than accumulating stale context.
