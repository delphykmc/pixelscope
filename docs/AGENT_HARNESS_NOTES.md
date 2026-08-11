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

### Qt UI harness lessons from P3-E

Production-like Qt interaction tests need to reproduce **event ownership and
lifetime**, not only widget state. The P3-E production-composition regression
exposed three reusable rules for future agents:

- A visible child widget with focus does not by itself prove that a
  `QShortcut` context is active. For real shortcut-event tests, make the
  top-level window the Qt active window (for example with
  `QApplication.setActiveWindow(window)`), assert that active-window state, then
  send the actual key event to the intended focused widget. This is especially
  important for `WidgetShortcut` / `WidgetWithChildrenShortcut` behavior on
  Windows under `pytest-qt`.
- Tree/list helpers can mutate application selection while a test is only trying
  to move keyboard focus. `QTreeWidget.setCurrentItem()` may therefore change the
  selected document set and indirectly disable presentation controls. When the
  test intends to preserve selection, use an explicit no-selection-update path
  such as `QItemSelectionModel.SelectionFlag.NoUpdate` and assert the selected
  IDs before and after the focus-only operation.
- A failed UI test can contaminate later tests if a top-level window survives.
  PixelScope owns several `ApplicationShortcut`s, so an aborted test that leaves
  a window alive can make unrelated Arrow/Number/PageUp/PageDown tests fail by
  intercepting later key events. Tests that manually manage a window lifetime
  should use `try/finally`, close/delete the window, process deferred-delete
  events when required, and avoid touching deleted Qt wrappers afterward.

When one new UI test fails and several later keyboard tests fail in apparently
unrelated features, first rerun the later tests without the failing predecessor.
If they pass, investigate leaked Qt objects/shortcuts and test cleanup before
assuming multiple production regressions. Keep shortcut-logic unit coverage
separate from at least one production-composition test that exercises the real
mouse/key/focus boundary.

### Qt / PySide harness lessons from P4-A

P4-A exposed two additional failure modes that are easy for later UI agents to
repeat because both look harmless at Python level:

- **Do not rewrite live constructor-time PySide signal topology by disconnecting
  stored bound methods and reconnecting wrappers.** On the owner Windows/PySide6
  environment, disconnecting a constructor-time connection during production
  composition caused a native access violation. `pytest` terminated with a
  Windows fatal exception, while `python -m pixelscope` could simply exit without
  a Python traceback or window. Prefer stable signal ownership: connect through
  the desired dispatch path when the widget is constructed, or expose explicit
  pre/post mutation signals from the owning widget and observe those without
  disconnecting existing MainWindow slots. Python-level method wrappers are fine
  only for call paths that actually resolve the method dynamically; they do not
  replace a callable already captured by an existing Qt signal connection.
- **Treat `pytest-qt` mouse helpers as bindings to the installed Qt/PySide API,
  not as a version-independent keyword interface.** The project PySide6 version
  rejected `modifier=` for `QTest.mousePress()` / `mouseRelease()` even though the
  intent was valid. For modifier-sensitive mouse regressions, use the compatible
  positional `Qt.KeyboardModifier` argument form (or verify the installed binding
  signature) and exercise the actual viewport gesture. Do not diagnose a product
  interaction regression from an `AttributeError` raised before Qt receives the
  event.

When Qt fails with a native access violation or the application exits before a
normal traceback, reproduce through both production composition/startup and the
smallest focused Qt test. Suspect signal lifetime/topology and Qt object ownership
before treating the failure as ordinary Python logic. Keep at least one production-
composition regression around any boundary that previously crashed before the
window became usable.

### 7. Treat entropy as recurring work

The PR #1–#9 audit exposed a representative failure mode: implementation moved
through P1-C, while several authoritative documents still said P1-A was in
progress and packed RAW was unimplemented. High throughput increases this kind
of drift unless documentation freshness and compatibility cleanup are explicit
deliverables.

## Agent provenance and GitHub attribution

PixelScope keeps human-authored work and agent-generated work distinguishable in
Git history and GitHub activity. Attribution is part of the engineering record,
not decorative PR text.

- Prefer a verified OpenAI GitHub App/bot identity as commit author or committer
  whenever the active tooling actually exposes that identity.
- When work must be committed through owner-authenticated tooling, use the
  repository-verified fallback from PR #9:
  `Co-authored-by: ChatGPT <noreply@openai.com>`.
- Never invent or guess a bot email address. Use only an identity already
  verified by the repository/tooling.
- PR comments and reviews do not have Git commit co-author metadata. Prefer a
  bot-authenticated account. When only owner-authenticated posting is available
  and automated posting is authorized, explicitly identify the body/comment as
  **ChatGPT-assisted** rather than presenting it as unaided owner activity.
- PR bodies for agent-assisted work record the actual commit attribution method,
  the account used for comments/reviews, and whether human commits were
  rewritten.
- Existing human-authored commits are never amended, rebased for author rewrite,
  given fabricated co-authors, or force-pushed merely to change provenance.
- Validation and final reports state the observed GitHub author/committer and
  the attribution fallback actually used.

This convention applies to future ChatGPT/Codex agents unless the repository
owner explicitly replaces it with another verified attribution mechanism.

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
- PR template requiring outcome, exclusions, evidence, deferred work, and agent
  provenance when applicable.

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
