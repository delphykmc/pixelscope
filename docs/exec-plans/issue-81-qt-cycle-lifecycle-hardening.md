# Execution plan: Issue #81 Qt lifecycle cycle hardening

Status: Active  
Owner: ChatGPT-assisted / repository owner  
Branch/PR: `test/fresh-process-batched-pytest` / PR #107 diagnostic branch  
Last updated: 2026-10-04

## Goal

Remove the application-owned Python reference cycles that keep large PySide/Qt object graphs alive until cyclic GC, so normal window/component teardown no longer depends on automatic generation-2 collection timing. Preserve all existing UI, RAW/YUV, IQA, Quick Compare, worker, and persistence behavior. Completion requires both structural evidence that the large retention roots are gone and repeated normal-GC validation from the focused reproducer through grouped and monolithic suites.

## Scope

### In scope

- Replace runtime instance-method monkey-patching patterns that store bound originals or closures back into the same QObject/QWidget ownership graph when those patterns create large strongly-connected components.
- Refactor the three measured retention roots in descending impact order:
  1. workflow polish + analysis/line-profile + native YUV semantics;
  2. remote/historical IQA controller and lifecycle wrappers;
  3. MultiCompareView + QuickCompare + Issue #77 follow-up wrappers.
- Add explicit extension points, delegation, signals, strategy objects, or native class methods where needed so behavior can be extended without wrapper-to-original cycles.
- Add deterministic `dispose()` / `uninstall()` only where runtime-installed signal/filter/timer ownership remains necessary; teardown must be idempotent and must not rely on automatic GC.
- Add repository-level harness guidance and mechanical/lifecycle regression coverage so future agents do not reintroduce the same pattern.
- Reassess the remaining small SCCs after the three application-owned roots are removed. Bounded third-party pyqtgraph cycles are not automatically defects if they no longer retain PixelScope application graphs and teardown remains safe.

### Out of scope

- `gc.disable()`, production-wide `gc.collect()`, arbitrary sleeps, timeout increases, or test-process isolation as the production fix.
- Rewriting pyqtgraph internals solely to obtain a zero-cycle process.
- Broad UI redesign or unrelated cleanup while changing ownership/lifecycle structure.
- Treating PR #107 fresh-process batching as the root-cause fix; it remains diagnostic/fallback execution infrastructure until lifecycle stability is demonstrated.

## Current state

Issue #81 was reduced from a moving full-suite native crash to a deterministic three-file reproducer under normal automatic GC:

- `tests/ui/test_p4a_review_selection.py`
- `tests/ui/test_p4a_review_selection_review_fixes.py`
- `tests/ui/test_p4b_comparison_set.py`

Controlled GC experiments established that automatic cyclic GC timing, not GC in general, is the critical trigger: disabling automatic cyclic GC or performing explicit collection at a known safe main-thread boundary passes, while normal automatic collection reproduces native access violations / heap corruption. Generation narrowing further showed that suppressing automatic gen2 collection is sufficient for the focused reproducer.

Object-graph diagnostics then established the retention mechanism:

- `MainWindow` had numerous direct `controller.window/_window -> MainWindow` return edges plus stored `_original_*` bound methods that also returned to `MainWindow`.
- Cutting those MainWindow-level return edges removed `MainWindow` itself but left the bulk of the graphics/UI graph retained, proving independent application-level SCCs below the window.
- G10/G11 SCC analysis showed that only a minority of unreachable objects are themselves in cycles; small SCC roots retain much larger downstream Qt/PySide graphs.
- The three dominant application-owned roots were measured as approximately 3666, 2132, and 938 retained objects before targeted cuts.

G13 removed only the measured Rank-1 runtime edges at test teardown under the normal GC thresholds `(700, 10, 10)`. The previous three-file reproducer then passed repeatedly, which is strong causal evidence but not sufficient to declare the issue fixed because changing graph size also changes GC timing.

G14 then measured cumulative structural reduction with automatic gen2 suppressed only for observation at the safe capture boundary:

- Level 1 (Rank 1 removed): `garbage=2580`, `cyclic_objects=233`; the remaining dominant roots retained 2132 and 938 objects.
- Level 2 (Rank 1+2 removed): `garbage=1394`, `cyclic_objects=107`; the 938-object Quick Compare root remained dominant.
- Level 3 (Rank 1+2+3 removed): `garbage=498`, `cyclic_objects=89`; the largest remaining application SCC retained only 79 objects, followed by six bounded pyqtgraph `ViewBox <-> LegendItem` cycles retaining about 52 objects each.

This staged reduction demonstrates that Rank 1/2/3 are independent real retention roots rather than one diagnostic artifact.

Relevant implementation patterns already confirmed in source include:

- `src/pixelscope/ui/workflow_polish.py`: captures original panel bound methods, installs `MethodType` wrappers on the same panel, and uses closures for cosmetic behavior.
- `src/pixelscope/app/yuv_input_semantics.py`: stores original MainWindow/panel bound methods and replaces those methods with controller methods.
- `src/pixelscope/ui/iqa_historical_results_lifecycle.py` and related IQA lifecycle layers: store original bound methods, create closures that capture lifecycle/controller state, and reassign runtime methods.
- `src/pixelscope/ui/quick_compare.py`: stores original `MultiCompareView` / MainWindow bound methods and installs closures back onto those owners.

These patterns are convenient incremental composition techniques, but repeated stacking across large QObject/QWidget graphs makes object destruction depend on Python cyclic GC instead of deterministic ownership boundaries.

## Invariants and constraints

- Keep CPython 3.10 x64, the pinned PySide/PyInstaller environment, and existing packaging contracts unchanged.
- Existing user-visible behavior and existing public/internal semantic contracts remain unchanged unless a separately reviewed behavior change is required.
- Expensive/numerical work remains off the GUI thread and background callables must not capture QWidget/QObject owners.
- Qt/PySide native object destruction must not depend on arbitrary automatic cyclic-GC timing.
- A QObject parent relationship does not justify an additional Python strong-reference return path if that closes a large application graph unnecessarily.
- New extension points should have one clear owner and directional dependencies. Avoid controller <-> view/window strong-reference loops where narrower dependencies or weak/non-owning references are sufficient.
- Do not store a bound method of an owner object inside a child/controller and then install the child/controller method or a closure back onto that same owner unless there is a deterministic uninstall contract and a demonstrated need.
- Runtime method replacement is not the default extension mechanism. Prefer class-native hooks, explicit delegates/strategies, stable Qt signals, or subclass/owned helper methods.
- Any remaining deliberate Python cycle that includes QObject/QWidget/PySide wrappers must be bounded, have deterministic teardown semantics, and be covered by lifecycle regression evidence.
- A focused PASS after refactoring is not proof of completion because changing allocation/retention can move the automatic-GC trigger. Structural retention evidence and broader repeated validation are mandatory.

## Proposed design

### Ownership model

Use explicit one-way ownership and extension contracts:

- The owning widget/window owns helpers/controllers that implement feature behavior.
- Helpers receive only the concrete dependencies they need rather than the entire MainWindow when practical.
- Panels expose stable extension points (signals, strategy/delegate interfaces, or ordinary class methods) instead of having instance methods replaced after construction.
- Cosmetic polish observes state or uses panel-native methods; it does not wrap and retain core bound methods.
- Semantics controllers provide data/behavior through an explicit adapter/delegate selected by the owner rather than saving an original bound method and replacing the owner's method.
- Lifecycle objects that install event filters, signals, timers, or external callbacks implement idempotent explicit teardown and disconnect/remove what they install.

### Rank 1 design direction

`workflow_polish` should stop replacing `ComparisonAnalysisPanel` and `LineProfilePanel` methods. Move empty-hint/status synchronization to panel-supported state notifications or small owned presentation helpers invoked from stable panel code. Native YUV semantics should stop saving panel bound originals and replacing `set_documents` / `refresh`; instead route semantic choice through an explicit analysis/line-profile adapter or another narrow panel/MainWindow hook whose ownership does not point back through a saved bound method.

### Rank 2 design direction

Collapse the IQA wrapper stack into explicit controller/lifecycle APIs. Methods such as result-open intent invalidation and settings-change handling should be called through stable signals/hooks or controller-owned methods, not `MethodType` replacement. IQA lifecycles should receive narrow controller/settings dependencies, avoid whole-window ownership where unnecessary, and expose deterministic teardown for installed connections/timers/workers.

### Rank 3 design direction

Move Quick Compare's geometry/render extension into explicit `MultiCompareView` policy hooks or controller APIs. Avoid storing `_original_prepare`, `_original_fixed_geometry`, or `_original_render_selection` bound methods and installing closures back onto the view/window. Event-filter ownership remains explicit and must be removed during controller teardown.

### Remaining cycles

After Rank 1/2/3, measure again before changing the remaining SCCs. Small `ViewBox <-> LegendItem` pyqtgraph cycles or small PixelScope controller cycles should be changed only if they retain application objects, survive expected teardown boundaries, or reproduce unsafe destruction. The target is deterministic lifecycle safety, not mathematically zero cycles.

## Implementation slices

1. **Harness contract and diagnostics baseline**
   - Files/components: `AGENTS.md`, harness notes/quality tests as appropriate, this execution plan, Issue #81 record.
   - Observable result: future implementation/review agents are explicitly prohibited from using cyclic-GC-dependent Qt ownership as the default extension pattern; G14 evidence and validation ladder are preserved.
   - Tests: docs checks; no production behavior change.

2. **Rank 1 — workflow polish / analysis / line-profile / YUV composition**
   - Files/components: `workflow_polish.py`, `comparison_analysis_panel.py`, `line_profile_panel.py`, `yuv_input_semantics.py`, composition call sites and focused tests.
   - Observable result: no Rank-1 owner->wrapper->closure/original-bound-method->owner SCC; all existing histogram, line-profile, YUV, and polish behavior remains unchanged.
   - Tests: relevant focused UI/unit tests; a structural/lifecycle regression; G11/G14-style measurement; three-file reproducer repeated in fresh processes under normal GC.

3. **Rank 2 — IQA lifecycle composition**
   - Files/components: IQA submission, historical result, mapping, scene-inspection controllers/lifecycles and their composition call sites.
   - Observable result: remove the ~2132-object retention root without changing IQA settings, submission, history, provenance, stale-result, or scene-inspection behavior.
   - Tests: existing focused IQA suites; lifecycle teardown test; structural retention measurement; three-file/grouped regression.

4. **Rank 3 — Quick Compare / MultiCompareView / Issue #77 composition**
   - Files/components: `quick_compare.py`, `multi_compare_view.py`, Issue #77 follow-up composition and tests.
   - Observable result: remove the ~938-object retention root while preserving 3-view layout, blink, Difference scheduling, drag/drop, display-gain, and input-filter behavior.
   - Tests: existing Quick Compare/Issue #77 UI tests; event-filter teardown; structural retention measurement; grouped regression.

5. **Residual lifecycle audit and mechanical guard**
   - Files/components: remaining app/ui runtime wrappers, tests/harness docs.
   - Observable result: remaining SCCs are classified as bounded/acceptable or refactored; no large PixelScope Qt graph is retained only by Python cycles after its owner lifetime ends.
   - Tests: add an AST/source architecture guard against new QObject/QWidget runtime instance-method replacement patterns that retain bound originals, with a narrow documented allowlist only if unavoidable; add teardown/weakref coverage for representative production composition.

6. **Validation expansion and PR #107 decision**
   - Files/components: test execution docs/CI only after runtime behavior is stable.
   - Observable result: focused, grouped, and monolithic runs are all understood. Fresh-process batching remains only if it has independent value; it is not used to hide a still-reproducible lifecycle defect.
   - Tests: validation ladder below.

## Validation plan

- Targeted automated tests per slice: all affected feature tests plus focused lifecycle/ownership regressions.
- Structural evidence after every rank: repeat the SCC/retention census at the same safe diagnostic boundary and compare retained-object counts to the G14 baseline.
- Focused native reproducer: run the three-file sequence repeatedly under normal automatic GC in fresh processes. A PASS is necessary but not sufficient.
- Grouped execution: use the PR #107 runner or equivalent fresh-process functional groups to detect a moved accumulation threshold if the original three-file sequence stops reproducing.
- Larger UI group(s): expand around any group that shows a native failure and minimize again only if necessary.
- Monolithic suite: run repeatedly under normal GC with no lifecycle mutation probe, no `gc.disable()`, and no unconditional collection workaround.
- Full checks from `docs/QUALITY.md`: Ruff, mypy, required focused/full pytest lanes, documentation checks, and any release checks required by the final change scope.
- Manual Windows checks: production startup, normal window close, Histogram/Line Profile, YUV open/analysis, IQA workflows, Quick Compare/3-view/blink/drag-and-drop, and clean application exit.
- Memory/lifecycle checks: representative windows/components should not require automatic gen2 collection to release application-owned graphs; worker/timer/filter/signal teardown must be quiescent before owner destruction.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Refactor changes GC timing and the current three-file reproducer disappears before the real defect is fully removed | Structural SCC/retention counts still show large application roots; grouped or monolithic suite later fails | Do not equate focused PASS with completion. Continue Rank 2/3 removal and expand validation through grouped/full runs. |
| Removing wrappers changes subtle UI behavior | Existing focused feature tests and manual Windows smoke | Preserve behavior slice-by-slice; introduce explicit hooks before deleting old wrappers; keep each slice independently reviewable. |
| Broad rewrite creates regressions that obscure the lifecycle result | Diff scope grows across unrelated features | Refactor one measured SCC rank at a time and keep behavior changes out of the lifecycle PR. |
| Weak references are applied mechanically and create premature object loss | Focused behavior/lifetime tests | Prefer explicit ownership/dependency narrowing. Use weak references only for genuinely non-owning relationships, not as a blanket cycle workaround. |
| Explicit `dispose()` becomes another ad-hoc cleanup layer | Teardown ordering becomes scattered or duplicated | Centralize owner-driven teardown, make it idempotent, and use it only for resources/connections that actually need explicit uninstall. |
| Static guard produces false positives or blocks legitimate Python composition | Guard failures on known-safe patterns | Define the guard around QObject/QWidget runtime method replacement + retained bound originals rather than banning closures or `MethodType` globally. |
| Third-party pyqtgraph cycles remain | G14 residual SCC census | Accept bounded library-local cycles when they do not retain PixelScope owners and repeated normal-GC validation is stable. |

## Progress log

- 2026-10-04: Issue #81 focused reproducer and automatic-gen2 trigger established; explicit safe-boundary collection remains non-failing.
- 2026-10-04: G6-G12 identified multiple application-owned SCCs created by controller/window backreferences, stored bound originals, runtime method replacement, and closures.
- 2026-10-04: G13 Rank-1 cycle cut made the prior three-file normal-GC reproducer pass repeatedly; treated as causal evidence, not completion, because GC timing changed.
- 2026-10-04: G14 staged cuts confirmed independent dominant roots. Rank 1 only left 2580 garbage / 233 cyclic objects with 2132- and 938-object roots. Rank 1+2 left 1394 / 107 with the 938-object root. Rank 1+2+3 left 498 / 89; largest residual application SCC retained 79 objects and bounded pyqtgraph cycles retained ~52 each.
- 2026-10-04: Owner chose long-term architecture repair over retaining a composition pattern that will become more fragile as features accumulate.

## Completion summary

Fill in at completion:

- Delivered behavior:
- Changed files:
- Validation results:
- Remaining limitations:
- Follow-up issues:
- Durable docs updated:
