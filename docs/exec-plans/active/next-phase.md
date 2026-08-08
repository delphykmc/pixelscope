# Execution plan: P2-B byte-budgeted decoded-source residency

Status: Active
Owner: ChatGPT-assisted implementation agent
Branch/PR: `feature/p2-b-source-residency-budget`
Last updated: 2026-08-08

## Goal

Replace `MainWindow`'s fixed seven-document decoded-source policy with a
deterministic native-source byte budget. Completion is observable when Files
residency badges track `ImageDocument.source`, protected sources remain usable
even above the soft budget, unprotected least-recently-used sources are released
and reload through the existing load path, and Settings persists the startup
budget through schema v4.

## Scope

### In scope

- Pure-core `ResidencyManager` for byte accounting, LRU ordering, protected
  eviction planning, and minimal diagnostics.
- Native `ImageDocument.source.nbytes` accounting for reloadable registered
  sources, with preview, Difference-map, transient-worker, Qt, and derived
  channel memory excluded.
- Protection for visible, selected, active/analysis, Difference-pair, and active
  load-target document IDs.
- Source release, dependent document-local cache invalidation, Files badge
  updates, and reuse of the existing tokenized normal-load path.
- A 1024 MiB default decoded-source budget, 128–32768 MiB validation, immutable
  startup injection, schema-v3-to-v4 migration, Performance UI, and restart
  indication.
- Deterministic unit/UI regression tests and durable documentation updates.

### Out of scope

- Preload, next-group prediction, a preload worker pool, or a preload setting.
- Full diagnostics UI, copy/export, failure history, worker-count controls, or
  process RSS tracking.
- Difference Map Cache redesign or coupling source eviction to Difference-map
  eviction.
- RAW expansion, sessions, remote/auth, packaging/signing, and startup-frame
  polish.

## Current state

PR #15 merged P2-A2 into `main` at
`1869764a74b01cebebaf8fa915b11a2a696be6cb`; this branch starts at that commit.
`MainWindow` previously owned `_resident_order`, `_resident_document_limit = 7`,
`_touch_resident()`, and `_evict_resident_documents()`. Successful normal loads
replace pending documents and the existing load-token/worker registry rejects
stale results. Eviction clears source, preview, Statistics/Histogram caches, and
source-derived channel views. `ApplicationSettings` schema v3 currently exposes
only the Difference Map Cache startup budget through frozen
`PerformanceSettings`.

The checkout also contains pre-existing untracked files under `docs/temp/` and
`pixelscope-p1f.zip`. They are outside this plan and must not be modified or
staged.

## Invariants and constraints

- Target CPython 3.10 x64 and keep expensive decode/analysis off the UI thread.
- Preserve native dtype, channel meaning, strides, endianness, alignment, and
  bounds; the manager stores only integer byte counts and imports no Qt.
- The budget is soft: protected sources and one oversized protected source may
  remain resident above budget.
- Only unprotected resident sources are eviction candidates, ordered oldest to
  newest. Manager planning and `MainWindow` mutation remain separate.
- Channel-split and Difference result documents are not independent source
  residency entries.
- Source eviction invalidates source-local derived state but does not evict a
  valid `DifferenceMapCache` entry solely because source bytes were released.
- Performance settings remain immutable startup snapshots; saves never mutate
  the current residency manager's budget.
- Existing human commits are not rewritten. Owner-authenticated commits use the
  repository's `Co-authored-by: ChatGPT <noreply@openai.com>` fallback.

## Proposed design

`core.residency.ResidencyManager` owns an ordered mapping from registered
document ID to resident source bytes. `record()` updates accounting, `touch()`
promotes an existing ID, `remove()` drops it, and `eviction_candidates()` plans
the oldest unprotected removals needed to reach the byte budget without
mutating documents. Read-only properties expose budget, used bytes, resident
count, over-budget bytes, and deterministic LRU IDs.

`MainWindow` owns actual `ImageDocument` mutation. It records exact
`int(document.source.nbytes)` for registered native sources and after successful loads, removes entries on reload
reset/failure/document removal, computes protected registered IDs from current
application state, applies planned eviction, invalidates Statistics/Histogram
and channel-view state, updates Files badges, and lets newly required pending
documents use `_ensure_loaded()` and the existing tokenized worker path.

Settings schema v4 adds `settings/performance/source_residency_mib`. Startup
converts both independent MiB preferences into frozen byte budgets. The
Performance page presents distinct **Decoded Source Memory** and **Difference
Map Cache** controls; either startup-only difference from the runtime snapshot
shows the existing restart message.

## Implementation slices

1. **Pure-core policy**
   - Files/components: `core/residency.py`, focused unit tests.
   - Observable result: exact deterministic accounting and protected LRU plans.
   - Tests: dtype/shape `nbytes`, ordering, changed sizes, boundaries,
     protection, oversized sources, and diagnostics.
2. **Settings v4 and startup injection**
   - Files/components: settings domain/repository, `PerformanceSettings`,
     Settings dialog, application composition, settings tests.
   - Observable result: validated 1024 MiB preference persists and applies only
     after restart, independently from Difference Map Cache.
   - Tests: fresh/migration/round-trip/invalid/future/reset, immutability,
     injection, UI controls, save/revert/reset/restart combinations.
3. **MainWindow integration**
   - Files/components: `MainWindow`, source-residency UI tests.
   - Observable result: byte-based protected eviction, badge updates, cache
     invalidation, and normal-path reload replace fixed-count behavior.
   - Tests: eviction/protection/soft oversize/reload/stale result/cache
     independence/fixed-seven regression.
4. **Durable state and evidence**
   - Files/components: product, architecture, decisions, current state, roadmap,
     user guide, quality contract, and this plan.
   - Observable result: no implemented P2-B behavior remains described as
     future or count-based authority; P2-C remains planned.
   - Tests: documentation contract and full repository validation.

## Validation plan

- Targeted automated tests: new ResidencyManager, schema-v4, source-residency,
  Settings, and Difference-cache independence tests.
- Full checks: `scripts/check_docs.py`, `pytest -q`, `ruff check .`,
  `ruff format --check .`, `mypy src`, `pip check`, and `git diff --check`.
- Manual Windows checks: startup, Settings terminology/default/restart state,
  high/low budgets, selected/visible/active/Difference protection, reload,
  oversized source, green Files badges, rapid navigation, and analysis regressions.
- Performance or memory checks: deterministic small-array byte budgets only;
  no wall-clock thresholds or process-RSS claims.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Manager/document accounting diverges | diagnostics and integration assertions | centralize record/remove/release helpers and remove stale entries defensively |
| A required source is evicted and reload-thrashes | per-protection and oversized tests | compute one explicit protected registered-ID set before planning |
| Source eviction corrupts Difference caching | cache-retention integration test | never invalidate Difference maps on source-only eviction |
| Schema migration loses P2-A2 values | schema-v3-to-v4 preservation test | construct v4 from validated v3 fields plus only the new default |
| Async stale results repopulate obsolete documents | token/cancellation regression test | retain the current load-token and worker-registry apply checks |
| Unrelated owner files enter the PR | status/diff/staging review | stage only explicit tracked P2-B paths |

## Progress log

- 2026-08-08: Verified PR #15 merged at `1869764a74b01cebebaf8fa915b11a2a696be6cb`,
  `origin/main` matches, no conflicting open PR exists, and the P2-B branch starts
  at that SHA.
- 2026-08-08: Recorded the pre-existing untracked-file exclusion and activated
  the P2-B implementation plan.
- 2026-08-08: Implemented and focused-validated pure-core byte/LRU accounting,
  schema v4 plus both startup budgets, Performance UI restart behavior, and
  protected `MainWindow` eviction/reload/invalidation integration. The focused
  residency/settings/Difference set passed 125 tests with two unrelated hover
  tests deliberately excluded after their baseline failures were reproduced.
- 2026-08-08: The documentation contract, Ruff lint, Ruff format, mypy, pip
  dependency check, diff whitespace check, compileall, and hidden application
  startup smoke passed. The mandatory Ruff format check exposed ten pre-existing
  `origin/main` formatting mismatches; they were normalized mechanically without
  behavior changes so the repository-wide formatter contract now passes.
- 2026-08-08: Full pytest was run both sandboxed and in the owner context. Both
  runs produced 293 passed and the same three pre-existing offscreen UI failures:
  floating Plots geometry restore and two pyqtgraph hover-coordinate assertions.
  These unrelated assertions were not skipped or rewritten to manufacture a
  passing result; they remain an explicit draft-PR validation limitation.

## Completion summary

- Delivered behavior: Exact native-source byte accounting; deterministic
  protected LRU soft budget; source eviction/reload/invalidation; schema-v4
  1024 MiB startup setting and minimal diagnostics.
- Changed files: Core residency/performance policy, application settings and
  lifecycle integration, Performance UI, focused tests, durable P2 docs, plus
  ten mechanical baseline-format normalizations required by the full contract.
- Validation results: Focused P2-B suite 125 passed / 2 unrelated tests
  deselected; all static/docs/dependency/startup-smoke checks passed; full suite
  293 passed / 3 unrelated offscreen UI failures.
- Remaining limitations: Manual visual Windows residency/settings matrix is not
  executed in this automated run; the three reproducible baseline UI failures
  prevent claiming a fully passing repository pytest contract.
- Follow-up issues: P2-C bounded next-group preload remains next. The existing
  P1-E geometry/hover test environment needs owner follow-up outside P2-B.
- Durable docs updated: Architecture, decisions, product, user guide, current
  state, roadmap, quality, UI status, and this execution plan.
