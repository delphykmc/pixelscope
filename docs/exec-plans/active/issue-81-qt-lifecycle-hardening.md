# Execution plan: Issue #81 Qt lifecycle hardening

Status: Branch-local hardening complete; stacked WP-C integration pending
Owner: ChatGPT-assisted implementation; repository owner validation
Branch/PR: `fix/issue-81-qt-lifecycle-hardening` / PR #82
Last updated: 2026-09-14

## Goal

Identify and remove the reproducible Windows `0xc0000374` Qt/PySide lifecycle failure
without masking it, while retaining the widget-ownership, event-driven test,
synthetic-worker, and realized-geometry improvements already established during the
investigation. Branch-local completion requires deterministic lifecycle regression
coverage, repeated normal-GC Windows full-suite passes, clean repository static gates,
final durable lifecycle documentation, and an independent blocker-free review.

PR #82 remains intentionally stacked on the WP-C boundary until this hardening is
incorporated there. Final Issue #81 closure is deferred until WP-C is subsequently
rebased/revalidated against current `main` according to the agreed integration order.

## Scope

### In scope

- Qt/PySide object ownership and destruction ordering exposed by UI teardown.
- `TaskWorker` / `QRunnable` auto-delete and signal-bridge affinity.
- Background callable capture of UI-owned `QObject` / `QWidget` instances.
- pyqtgraph-owned callback/menu/widget graphs that outlive their PixelScope owner.
- Cancel-versus-physical-quiescence semantics and late-result authority after final UI
  disposal.
- `pytest-qt` widget cleanup, DeferredDelete, and Python cyclic-GC interaction.
- Deterministic focused regression/stress coverage for the proven lifecycle defects.
- Final `docs/QUALITY.md` lifecycle contract and branch-local validation evidence.

### Out of scope

- WP-C Quick Compare behavior beyond preserving its current stacked baseline.
- Arbitrary sleeps, timeout inflation, `gc.disable()`, blanket production/test-boundary
  `gc.collect()`, fatal skips, or unproven global-pool waits as fixes.
- Packaging changes or packaging-tool execution.
- Final WP-C-to-`main` integration validation; that occurs after PR #82 is incorporated
  into WP-C according to the stacked merge/rebase flow.

## Final branch-local state

The original native failure was not reduced to one single feature bug. WinDbg and
lifetime probes established a lifecycle failure class in which Python cyclic GC and
Shiboken/Qt wrapper destruction on the GUI thread could overlap worker-thread
finalization and Qt object destruction. The investigation then identified and fixed
multiple concrete defects that made that overlap unsafe or left large wrapper graphs
for arbitrary GC timing:

1. **Deferred Qt cleanup crossing UI-test boundaries**
   - `tests/ui/conftest.py` drains `QEvent.DeferredDelete` after pytest-qt widget
     cleanup so destruction does not spill into a later local event loop.
   - Async assertions remain state/event-driven rather than being hidden by longer
     waits or sleeps.

2. **Synthetic cancellation GIL hot-spin**
   - Test workers no longer spin indefinitely around cancellation checkpoints and
     starve the GUI/event loop.

3. **Preallocated widget ownership and geometry**
   - Preallocated viewers/plots have explicit Qt ownership.
   - Geometry-dependent Line Profile coverage realizes the PlotWidget before mapping
     scene/view coordinates.

4. **TaskWorker signal-bridge affinity**
   - `TaskSignals(QObject)` is application-owned so QRunnable auto-deletion cannot
     destroy the GUI-thread-affine signal bridge on a pool thread.
   - `deleteLater()` schedules signal-object destruction on its Qt affinity thread.

5. **Background QWidget capture**
   - Difference numerical work no longer closes over `DifferencePanel(QWidget)`;
     background callables receive/snapshot non-UI state instead.

6. **ImageViewer ROI wrapper cycle**
   - The presentation-only ROI no longer uses `pyqtgraph.RectROI`, which created an
     unused Handle and parentless QMenu callback graph.
   - A plain `QGraphicsRectItem` preserves the existing ROI behavior because
     `RoiViewBox` owns the actual interaction.

7. **Histogram/pyqtgraph final disposal**
   - `ComparisonAnalysisPanel` stores PixelScope-owned mouse callbacks and disconnects
     exactly those callbacks at final shutdown.
   - Parentless ViewBox menus and PlotWidgets are explicitly closed/deferred-deleted,
     and Python plot/legend/hover references are released.
   - Final disposal is idempotent and is not tied to ordinary dock hide/show,
     floating, or redocking.

8. **Cancel is not quiescence**
   - A worker that was already running may still queue success/error after cancel.
   - After final `ComparisonAnalysisPanel` disposal, refresh/result/error callbacks
     lose UI authority and become inert rather than rendering into released plots or
     mutating result/cache state.

The resulting production fixes do not depend on `gc.disable()`, blanket
`gc.collect()`, arbitrary sleeps, timeout inflation, fatal-exception suppression, or
unconditional whole-pool waits.

## Durable lifecycle invariants

- A background worker callable must not retain a `QObject`/`QWidget` owner merely to
  access numerical/helper behavior; snapshot plain data or a non-UI callable before
  dispatch.
- Preallocated Qt widgets/resources need explicit ownership, and Qt-affine QObject
  destruction must occur on the owning Qt thread through parent ownership or
  affinity-safe deferred deletion.
- Cancellation is advisory. It changes result authority immediately but does not prove
  physical worker quiescence.
- Late results/errors after final UI disposal must be rejected at the feature owner;
  a physically running worker must not regain authority over disposed UI.
- Shared/application-owned pools are quiesced only at the appropriate owner boundary;
  one feature/window must not indiscriminately join or cancel unrelated work.
- Third-party Qt wrapper graphs such as pyqtgraph callbacks and parentless menus must
  be explicitly disposed when PixelScope owns their final lifecycle boundary.
- Test harness cleanup may make Qt destruction deterministic, but must not conceal a
  production ownership defect.
- `gc.disable()`, unconditional `gc.collect()`, arbitrary sleeps, and timeout inflation
  are diagnostics/workarounds, not lifecycle fixes.

## Validation evidence

### Runtime/lifecycle validation

Repository-owner Windows validation used normal automatic Python GC. At lifecycle
HEAD `bb96841`:

- full pytest run 1: `1273 passed, 1 skipped`;
- full pytest run 2: `1273 passed, 1 skipped`;
- full pytest run 3: `1273 passed, 1 skipped`.

The one skip is the expected Windows directory-symlink privilege case. No
`0xc0000374`, fatal exception, or new Qt teardown signature occurred in the three
runs. Total run time remained approximately flat rather than increasing across runs.
Focused Issue #81 teardown tests also cover GUI-thread signal destruction,
pyqtgraph-resource release, idempotent histogram shutdown, and rejection of a late
worker result after final UI disposal.

### Static/docs validation

Static-only cleanup commit `01ce5eb` changed formatting/static configuration but no
runtime semantics. Exact-head validation recorded in PR #82 passed:

- `python -m ruff check .`;
- `python -m ruff format --check .`;
- `python -m mypy src` — 135 source files;
- `python scripts/check_docs.py`;
- `python -m pip check`;
- `git diff --check`.

Because `01ce5eb` was static-only, the owner-completed full pytest 3x result at
`bb96841` was not repeated merely for formatting cleanup.

### Independent review

Independent review of exact HEAD `01ce5eb` found no new runtime/code merge blocker.
The reviewer specifically confirmed the lifecycle direction and validation evidence,
with only durable-document/PR-state reconciliation remaining before the stacked merge.

## Risks and integration boundaries

| Risk | Current control |
|---|---|
| Deferred Qt destruction leaks into a later UI test | pytest-qt boundary drains `DeferredDelete`; focused lifecycle coverage |
| Worker-thread finalization destroys GUI-affine QObject | application-owned `TaskSignals` plus affinity-safe `deleteLater()` |
| Worker closure retains/destructs QWidget graph | background callable capture regression and Difference snapshotting |
| Third-party pyqtgraph graph waits for arbitrary cyclic GC | explicit final callback/menu/plot disposal |
| Cancelled worker finishes after UI teardown | final-disposal authority barrier rejects late callbacks |
| One window blocks/cancels unrelated application work | cancellation remains feature-local; shared-pool quiescence belongs to owner boundary |
| Stacked WP-C scope leaks into hardening | PR #82 remains stacked and is reviewed against `2692b17`; integration validation follows the agreed WP-C flow |

## Progress log

- 2026-09-14: Branch-local Issue #81 hardening reached exact static/review HEAD
  `01ce5eb`. Owner normal-GC full pytest had already passed three consecutive runs at
  lifecycle HEAD `bb96841` (`1273 passed, 1 skipped` each). Exact-head Ruff
  check/format, mypy, docs contract, pip check, and diff check passed. Independent
  review found no new runtime/code merge blocker and requested durable documentation
  reconciliation only.
- 2026-09-13: ROI lifetime probe identified `pg.RectROI` → Handle → parentless QMenu
  cycles in presentation-only ImageViewer ROIs. Commit `0f2263e` replaced the unused
  interactive ROI graph with `QGraphicsRectItem` while preserving ROI authority in
  `RoiViewBox`.
- 2026-09-13: Histogram lifetime probes identified deterministic
  `ComparisonAnalysisPanel`/pyqtgraph callback and menu retention. Production final
  disposal was added in `bb96841`. The first full-suite attempt then exposed a real
  cancel-versus-quiescence regression: a physically running worker could deliver a
  queued result after plots were disposed. The same change was hardened with a
  late-result barrier and executable regression coverage before the successful
  repeated full-suite validation.
- 2026-09-13: Difference worker inspection proved a numerical closure retained
  `DifferencePanel(QWidget)`; commit `cfee792` snapshots the required non-UI callable
  before worker dispatch.
- 2026-09-13: A direct destruction-thread probe proved parentless
  `TaskSignals(QObject)` could be destroyed on the pool thread when an auto-delete
  `TaskWorker` lost its final reference. Commit `2e95ed7` made the signal bridge
  application-owned and scheduled affinity-safe deletion. This fixed a real defect but
  was correctly treated as only one contributor because full-suite native failure
  still reproduced afterward.
- 2026-09-13 (independent re-investigation): Windows CPython 3.10.11 / PySide6 6.4.2
  independently reproduced `0xc0000374` with main-thread GC and concurrent IQA worker
  activity. Focused negative controls passed and did not by themselves establish root
  cause. Temporary probes remained outside committed source.
- 2026-09-13: Explicit parent ownership reduced the large post-MainWindow widget tree,
  synthetic cancellation hot-spin was removed, deferred deletion was drained at test
  boundaries, and geometry-sensitive hover coverage was changed to realized geometry.

## Completion summary

- **Delivered behavior:** Branch-local Qt/PySide lifecycle hardening is complete. The
  known native-failure contributors and wrapper-retention defects found by this
  investigation have deterministic production fixes and focused regressions.
- **Validation:** Normal automatic-GC Windows full pytest passed three consecutive runs
  at `bb96841`; exact-head static/docs gates passed at `01ce5eb`; independent review
  found no runtime/code blocker.
- **Remaining limitation:** This is still a stacked PR. The validation above proves the
  hardening branch against its intended WP-C boundary, not final integration with a
  future rebased `main`.
- **Next step:** Incorporate PR #82 into WP-C first, then rebase/revalidate WP-C against
  current `main` before deciding final Issue #81 closure and resuming PR #80 merge
  readiness.
- **Follow-up:** PR #80 remains paused until the hardening is incorporated and the
  stacked integration flow is completed.
- **Durable docs:** This plan and `docs/QUALITY.md` record the final branch-local
  lifecycle contract. Temporary forensic probes remain non-production and untracked.
