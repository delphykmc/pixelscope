# Agent harness engineering notes

## What a harness is

For coding agents, the harness is the environment that turns a broad request into reliable, reviewable work. It is not one prompt or one tool. It includes:

- A navigable repository and explicit architecture boundaries.
- Short persistent instructions that point to deeper sources of truth.
- Structured specifications, decisions, and execution plans.
- Deterministic setup, commands, fixtures, tests, and linters.
- Runtime observability and failure evidence.
- Small reviewable changes, PR conventions, and human checkpoints.
- Continuous cleanup of stale rules, duplicate utilities, and architectural drift.

The model produces code inside this system. The harness makes good behavior easier, bad behavior visible, and recovery inexpensive.

## Lessons from OpenAI's Codex experience

OpenAI reported building an internal product with agent-written application code, tests, CI configuration, documentation, observability, and tooling. The main lesson was not that review or engineering discipline disappeared. Human effort moved toward specifying intent, designing the environment, and creating feedback loops.

### 1. Give agents a map, not a manual

A large `AGENTS.md` consumes context, makes every rule look equally important, becomes stale, and is difficult to check. Keep it short and use it as a table of contents. Store durable knowledge in focused documents under `docs/`.

PixelScope application:

- `AGENTS.md` identifies mandatory constraints and directs the agent to relevant docs.
- `docs/index.md` defines document ownership and task-based reading paths.
- Product, architecture, decisions, packaging, quality, and plans remain separate.

### 2. Make the repository the system of record

Important context must survive chat sessions and model changes. Architectural invariants, accepted decisions, workflow contracts, and test commands should be committed beside the code rather than retained in prompts or memory.

A useful document answers one of these questions:

- What must the product do?
- Where does this responsibility live?
- Why was this design chosen?
- How is the work divided and validated?
- What is intentionally deferred?

### 3. Optimize for agent legibility

Readable software is easier for humans and agents to change safely. Prefer explicit ownership, predictable names, versioned schemas, narrow interfaces, and local invariants over hidden coupling and clever indirection.

For PixelScope this means preserving boundaries among `io`, `core`, `workers`, `ui`, `app`, and `remote`; keeping numerical code outside widgets; and making asynchronous request identity and stale-result rules explicit.

### 4. Enforce architecture mechanically

Prose is necessary but insufficient. Important constraints should be represented by tests, static checks, dependency rules, schemas, or narrow interfaces whenever possible.

Examples:

- Test dtype promotion rather than only documenting overflow safety.
- Test stale-result rejection rather than only describing generation IDs.
- Pin Python and packaging versions in machine-readable configuration.
- Add smoke tests for critical UI workflows.

### 5. Use execution plans for long work

Long tasks fail when decisions and discoveries remain only in conversation. A checked-in execution plan should define goal, exclusions, current state, invariants, implementation slices, validation, risks, and progress. It is a working artifact, not an upfront ceremony.

Use a plan when work spans components, multiple commits or sessions, unresolved design choices, migrations, or high regression risk.

### 6. Improve feedback loops before increasing autonomy

Agent autonomy should rise only after the repository can quickly answer:

- Did the change compile and run?
- Did targeted and full tests pass?
- Did a user-visible contract change?
- Did performance, memory, or thread behavior regress?
- Can a reviewer understand and revert the change?

More detailed prompts cannot compensate for slow, flaky, or absent feedback.

### 7. Treat entropy as recurring work

Higher code throughput also creates duplicate helpers, local conventions, dead compatibility paths, stale documents, and overfitted tests faster. Schedule cleanup and make agents remove temporary scripts and revise obsolete rules in the same PR.

## PixelScope adoption checklist

### Already strong

- Pinned CPython and dependency versions.
- Clear package boundaries and UI/thread constraints.
- Extensive pytest, Ruff, mypy, and pip validation.
- Deterministic image fixtures and UI smoke coverage.
- Small phase-based PRs with explicit scope exclusions and validation reports.

### Added by this harness foundation

- Short `AGENTS.md` as a navigation map.
- Documentation system-of-record index.
- Standard execution-plan template.
- Change-to-check quality contract.
- Durable notes for sharing the method with colleagues.

### Next improvements

1. Create an active execution plan for the remaining P1-B2 work.
2. Add a lightweight script or test that verifies links and required documentation files.
3. Define PR and issue templates that require observable behavior, exclusions, and validation evidence.
4. Identify architecture constraints that can be checked mechanically, such as forbidden Qt imports in numerical core modules.
5. Add periodic technical-debt review for duplicate helpers, stale docs, oversized modules, and fragile UI tests.
6. Capture important runtime diagnostics for worker queues, cache budgets, stale-result drops, and load failures.

## Colleague-sharing outline

A concise internal presentation can use this sequence:

1. **Problem:** agents generate code quickly, but context loss and weak feedback create rework.
2. **Definition:** the harness is documentation, architecture, tooling, tests, observability, and review workflow surrounding the model.
3. **Key shift:** humans increasingly specify intent and design feedback loops; agents execute bounded work.
4. **Repository pattern:** short `AGENTS.md` → structured docs → execution plan → implementation → automated evidence → small PR.
5. **PixelScope example:** phase-scoped PRs, explicit exclusions, deterministic fixtures, UI smoke tests, and architecture notes.
6. **Measured outcomes:** review time, test-pass rate, rollback/rework rate, escaped regressions, plan accuracy, and documentation freshness—not generated lines of code.
7. **Caution:** an agent-written codebase is not an unreviewed codebase; autonomy must follow observability and guardrails.

## Practical principle

> Do not spend most of the effort making the prompt longer. Make the repository easier to understand, the desired behavior easier to specify, and incorrect changes faster to detect.
