# Execution plan: Issue #81 Qt lifecycle hardening

Status: Active
Owner: ChatGPT-assisted implementation; repository owner validation
Branch/PR: `fix/issue-81-qt-lifecycle-hardening` / PR #82
Last updated: 2026-09-13

## Goal

Identify and remove the reproducible Windows `0xc0000374` heap-corruption cause in
the Qt/IQA asynchronous teardown path without masking it, while retaining the
already-established widget ownership, event-driven test, synthetic-worker, and
realized-geometry improvements. Completion requires repeatable focused stress,
static checks, repeated full Windows pytest, final lifecycle documentation, and an
independent blocker-free review.

## Scope

### In scope

- `IqaWorkspaceController` and historical-result resolver cancellation,
  quiescence, queued-signal, and destruction ordering.
- `TaskWorker` / `QRunnable` auto-delete and Python-wrapper lifetime at UI teardown.
- Application-owned Remote IQA and numerical pool ownership in production and tests.
- `pytest-qt` widget cleanup, DeferredDelete, and Python GC interaction.
- A deterministic minimal reproducer and regression/stress coverage for the proven
  cause.
- Final `docs/QUALITY.md` lifecycle contract and validation evidence.

### Out of scope

- WP-C Quick Compare behavior beyond preserving its current stacked baseline.
- Arbitrary sleeps, timeout inflation, unconditional per-test `gc.collect()`, fatal
  skips, or unproven global-pool waits.
- Packaging changes or packaging-tool execution.
- Rebase/semantic-port to `main` until the lifecycle fix passes its branch-local
  gates.

## Current state

PR #82 is a Draft stacked on `codex/issue-77-wp-c@2692b17`; branch HEAD `1145064`
contains four preliminary hardening commits. Explicit parents reduced a destroyed
`MainWindow` from roughly 1290 surviving widgets to transient menus, the synthetic
cancellation hot-spin was removed, deferred deletion is drained at UI-test
boundaries, and geometry-sensitive hover coverage now realizes its PlotWidget.

The remaining blocker is a repeatable Windows `0xc0000374` during P5-E/IQA tests.
Observed crashes combine a main-thread pytest-qt event loop/GC with active result
loading and, in one run, a concurrent historical resolver. The lifecycle hypothesis
is not yet a root-cause conclusion.

Production constructs one application-owned Remote IQA pool and injects it into the
workspace, scene-inspection, and historical controllers. Direct `MainWindow()` test
composition currently falls back to the application-owned analysis pool. Controller
shutdown requests cancellation and immediately discards worker references; it does
not prove worker quiescence.

## Invariants and constraints

- Target CPython 3.10 x64 and the repository-pinned PySide6 runtime.
- Expensive IQA result/NPZ work remains off the UI thread and bounded.
- Cancellation stays advisory; generation/active checks remain result-authority.
- Window/controller destruction must not overlap feature-owned worker completion or
  queued delivery into destroyed receivers.
- Shared application pools must not let one window indiscriminately cancel or join
  unrelated work owned by another live window.
- Existing explicit QWidget ownership fixes remain in place.

## Proposed design

No final design is selected before reproduction. Instrument worker start/finish,
controller shutdown, pool activity, and receiver destruction in a focused diagnostic
test. Compare controller-local worker retention/quiescence against pool-wide waiting,
and verify whether `autoDelete=True` plus dropped Python references is necessary for
the fault. The final API should express controller-owned cancellation and quiescence;
pool-wide barriers are acceptable only at the actual application-owner shutdown
boundary and only with evidence.

## Implementation slices

1. **Reproduction and lifecycle proof**
   - Files/components: P5-E focused tests and temporary diagnostics.
   - Observable result: smallest repeatable predecessor/test sequence and a concrete
     invalid lifetime/order, not only correlated stacks.
   - Tests: repeated P5-E clusters plus isolated production-composition close.
2. **Worker/controller lifecycle fix**
   - Files/components: `task_worker.py`, IQA workspace/history controllers, pool
     owner as required by the proven cause.
   - Observable result: cancellation retains safe ownership until physical finish;
     shutdown has an explicit bounded quiescence result.
   - Tests: deterministic running-loader/resolver teardown and queued delivery.
3. **Harness and durable contract**
   - Files/components: focused UI stress tests, `docs/QUALITY.md`, this plan.
   - Observable result: tests encode the real lifecycle boundary without sleeps,
     blanket GC, skips, or unrelated global waits.
4. **Integration and merge ordering**
   - Files/components: Git history and PR #82 metadata.
   - Observable result: small attributed commits; investigation/root-cause comment;
     exact-head gates; semantic port/rebase to latest `main`; PR base changed to
     `main`; independent review; PR #82 merged before PR #80 resumes.

## Validation plan

- Targeted automated tests: repeated P5-E historical/review regression clusters,
  new worker/controller teardown stress, and existing Qt ownership/geometry tests.
- Full checks: `scripts/check_docs.py`, full `pytest -q`, Ruff check and format check,
  `mypy src`, `pip check`, and `git diff --check`.
- Manual Windows checks: repeated production-composition window close while IQA open
  and resolver/load work are active; observe clean exit and no late presentation.
- Full suite: at least two exact-head Windows runs without native failure.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| A fixture-only workaround hides production teardown | production-composition close regression | put ownership/quiescence in production controllers |
| Pool-wide wait couples independent windows | concurrent-owner test | track and quiesce controller-owned tasks |
| Auto-delete change leaks runnables | weakref/destruction stress and pool completion | retain only through physical finish, then release deterministically |
| Queued signals arrive after receiver teardown | destruction/late-result assertions | disconnect or drain only at the proven owner boundary |
| Stacked WP-C scope leaks into hardening | base-to-head semantic/stat diff | port only hardening commits to latest `main` before merge |

## Progress log

- 2026-09-13 (independent re-investigation): Confirmed local `2e95ed7` versus
  remote `1145064`, and read Issue #81, PR #82/current correction, and PR #80.
  Windows CPython 3.10.11 / PySide6 6.4.2 `pytest -x -vv` independently reproduced
  `0xc0000374` (exit -1073740940) at the partial-history test, with main-thread GC
  and a concurrent manifest reader. P5-E alone: 11 passed in 13.05s; P5-B plus
  P5-E: 23 passed in 19.86s; all P5 UI modules: 63 passed in 48.07s. Synchronous
  IQA widget create/populate/delete probes completed 100 iterations each for v2,
  v2 with refresh, and v1 with refresh. These negative controls do not establish
  a root cause or a passing full-suite gate. Native-stack and predecessor-sequence
  diagnostics are in progress; temporary probes remain outside committed source.
  Independent read-only audit found a separate queued-clear leak in the local
  candidate's application-parented TaskSignals, whose cleanup only runs in
  `TaskWorker.run()`; this is not yet tied to the native crash. Findings recorded
  in PR #82 comment 5649654485.
- 2026-09-13: Confirmed local branch `fix/issue-81-qt-lifecycle-hardening@1145064`,
  PR #82 Draft stacked base, latest lifecycle hypothesis, and PR #80 validation pause.
- 2026-09-13: Initial code audit confirmed production Remote IQA pool injection differs
  from direct-test `MainWindow()` fallback, while IQA shutdown cancels and immediately
  drops controller references without a controller-local quiescence contract.
- 2026-09-13: A direct destruction-thread probe proved the parentless
  `TaskSignals(QObject)` was destroyed on the pool thread when an auto-delete
  `TaskWorker` lost its final reference (observed GUI thread 17212 versus destruction
  thread 26120). Local commit `2e95ed7` corrected that operation and passed focused
  stress, but an owner full run on the same commit reproduced `0xc0000374` in P5-E.
  The finding is therefore a partial lifecycle defect, not the fatal root cause.
  The overclaim was corrected in PR #82; the commit remains local-only while the
  actual minimal predecessor sequence is investigated.

## Completion summary

- Delivered behavior: Pending.
- Changed files: Pending.
- Validation results: Pending.
- Remaining limitations: Pending.
- Follow-up issues: PR #80 remains paused until PR #82 merges.
- Durable docs updated: Pending final root-cause contract.
