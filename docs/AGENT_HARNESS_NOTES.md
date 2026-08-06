# Agent harness engineering notes

## Definition

For coding agents, the harness is the environment that turns a broad request
into reliable, reviewable work. It is not one prompt or one tool. It includes:

- A navigable repository and explicit architecture boundaries.
- Short persistent instructions pointing to focused sources of truth.
- Current-state records, product specifications, decisions, and execution plans.
- Deterministic setup, fixtures, tests, linters, and completion evidence.
- Runtime observability and failure diagnostics.
- Small reviewable changes, PR conventions, and human checkpoints.
- Recurring cleanup of stale rules, duplicate utilities, compatibility paths,
  and architectural drift.

The model produces code inside this system. The harness makes correct behavior
easier, incorrect behavior visible, and recovery inexpensive.

## OpenAI Codex lessons

OpenAI's
[Harness engineering](https://openai.com/index/harness-engineering/) report
describes an internal product whose application code, tests, CI,
documentation, observability, and tools were written by Codex. Human work moved
toward specifying intent, designing the environment, and building feedback
loops. The associated Codex guidance also emphasizes configured development
environments, reliable tests, and repository-level instructions.

### 1. Give agents a map, not a manual

A large `AGENTS.md` consumes context, makes every rule appear equally
important, becomes stale, and is difficult to verify. PixelScope therefore uses
`AGENTS.md` as a short table of contents and keeps durable knowledge under
`docs/`.

### 2. Make repository knowledge the system of record

Important context must survive chat sessions, model changes, and parallel work.
A durable document should answer one of these questions:

- What does the product do now?
- Where does a responsibility live?
- Why was a design chosen?
- What work is active, complete, or deferred?
- What evidence is required before completion?

`docs/CURRENT_STATE.md` is the dated planning entry point. Product,
architecture, decisions, roadmap, quality, UI notes, and execution plans have
separate ownership.

### 3. Optimize for agent legibility

Prefer explicit ownership, predictable names, narrow interfaces, versioned
schemas, and local invariants over hidden coupling. For PixelScope this means
preserving boundaries among `io`, `core`, `workers`, `ui`, `app`, and `remote`;
keeping numerical code outside widgets; and making generation, cache, and
stale-result rules explicit.

### 4. Enforce architecture mechanically

Prose is necessary but insufficient. Important constraints should be tests,
static checks, schemas, or narrow interfaces where practical.

PixelScope examples include:

- Overflow-safe Difference tests and native metric chunking.
- Stale-result and loading-order UI tests.
- Bit-exact unpacked/MIPI RAW fixture equivalence.
- Fixed Python and packaging versions in machine-readable configuration.
- `scripts/check_docs.py` and `tests/unit/test_docs_contract.py` for required
  docs and local links.

### 5. Use execution plans for long work

Long tasks fail when decisions and discoveries remain only in chat. A checked-in
plan is a live artifact containing goal, exclusions, current code references,
invariants, slices, validation, risks, decisions, and progress.

Use a plan when work crosses components, spans sessions, changes persistence or
schemas, or carries high regression risk.

### 6. Improve feedback loops before autonomy

More autonomy is justified only when the repository can answer quickly:

- Did the targeted behavior change as intended?
- Did focused and full checks pass?
- Did a public contract or durable document change?
- Did memory, thread, cache, or persistence behavior regress?
- Is the change understandable and reversible?

Longer prompts do not compensate for slow, flaky, or missing feedback.

### 7. Treat entropy as recurring work

The PR #1–#9 audit exposed a representative failure mode: implementation moved
through P1-C, while several authoritative documents still said P1-A was in
progress and packed RAW was unimplemented. High throughput increases this kind
of drift unless documentation freshness and compatibility cleanup are explicit
deliverables.

## PixelScope adoption status

### Existing strengths

- Pinned CPython/dependency versions and strict packaging constraints.
- Clear package boundaries and bounded worker pools.
- Extensive pytest, Ruff, mypy, pip, UI smoke, and performance coverage.
- Deterministic image and RAW fixtures.
- Phase-scoped PRs with explicit exclusions and validation summaries.
- Native Difference cache diagnostics and reloadable source residency.

### Added by the harness foundation

- Short navigational `AGENTS.md`.
- Documentation index and dated current-state record.
- Quality/completion contract and execution-plan template.
- Active plan for the next verified phase.
- Mechanical required-doc/local-link check.
- PR template requiring outcome, exclusions, evidence, and deferred work.

### Next harness improvements

1. Add a mechanical architecture-boundary check, beginning with forbidden Qt
   imports from numerical `core` and `io` modules.
2. Add a small technical-debt tracker with owner, trigger, and removal
   condition for compatibility bridges.
3. Capture runtime diagnostics for worker queues, cache budgets, stale-result
   drops, and load failures.
4. Add CI execution of the documentation contract and standard validation
   matrix when a supported runner is available.
5. Measure review/rework rate, escaped regressions, validation completeness,
   and document freshness rather than generated lines or commit count.

## Colleague-sharing outline

1. **Problem:** code generation is fast; context loss and weak feedback create
   rework.
2. **Definition:** the harness is the repository, documentation, architecture,
   tooling, tests, observability, and review workflow around the model.
3. **Role shift:** humans specify intent and feedback loops; agents execute
   bounded work.
4. **Repository pattern:** `AGENTS.md` map → current state → focused docs →
   execution plan → implementation slices → automated evidence → small PR.
5. **PixelScope example:** PR-scoped delivery, deterministic fixtures, UI smoke
   tests, cache invariants, RAW bit-exact checks, and explicit exclusions.
6. **Failure example:** completed packed RAW and P1-B work remained documented
   as future scope until a cross-PR audit.
7. **Metrics:** review time, first-pass validation, rollback/rework,
   documentation freshness, and escaped regressions.
8. **Caution:** agent-written does not mean unreviewed; autonomy follows
   observability and guardrails.

## Practical principle

> Do not spend most of the effort making the prompt longer. Make the repository
> easier to understand, the desired behavior easier to specify, and incorrect
> changes faster to detect.
