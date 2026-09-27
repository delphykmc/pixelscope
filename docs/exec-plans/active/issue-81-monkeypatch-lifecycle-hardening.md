# Issue #81 follow-up — runtime monkey-patch lifecycle hardening

## Status

Active investigation / implementation plan.

Tracking issue: #81
Forensic PR: #88 (closed; evidence only, not the implementation branch)
Implementation PR: #89
Implementation branch: `fix/issue-81-monkeypatch-lifecycle`
Base: `main@d51064d62291ed4057f2ddc215bc015143e634ef`

## Problem statement

Windows native crashes and hangs have been reproduced after production-composition Qt teardown. AppVerifier/dump analysis points to invalid-pointer failures surfacing later in unrelated CPython locations. A strong current hypothesis is that persistent runtime instance monkey-patching creates Python reference cycles that are only broken by cyclic GC. If those cycles contain PySide/Shiboken wrappers, final reference release may occur on an arbitrary worker thread rather than deterministically on the GUI thread.

Representative graph:

```text
MainWindow / QObject target
  -> patched callable stored on the instance
  -> closure or bound method
  -> controller / lifecycle owner
  -> MainWindow / QObject target
```

The original Issue #81 contract already forbids arbitrary Python-wrapper finalization for GUI-affine QObject destruction, but it did not explicitly cover runtime instance-method replacement as a source of GC-only cycles.

## Confirmed production inventory — lower bound

Manual cross-checking has confirmed persistent method replacement in at least the following production files. This is a lower bound; the inventory remains open until the static audit and implementation review agree.

- `src/pixelscope/ui/review_selection.py`
- `src/pixelscope/ui/difference_curation_lifecycle.py`
- `src/pixelscope/ui/recent_entries.py`
- `src/pixelscope/ui/workflow_polish.py`
- `src/pixelscope/ui/folder_display_tags.py`
- `src/pixelscope/ui/multiview_reorder_stability.py`
- `src/pixelscope/ui/quick_compare.py`
- `src/pixelscope/ui/issue77_ui_design_followup.py`
- `src/pixelscope/ui/beta_workspace_hardening.py`
- `src/pixelscope/app/registration_controller.py`
- `src/pixelscope/app/raw_input_compatibility.py`
- `src/pixelscope/app/yuv_input_semantics.py`
- `src/pixelscope/app/yuv_difference_semantics.py`
- `src/pixelscope/app/yuv_runtime_contracts.py`
- `src/pixelscope/ui/iqa_remote_settings.py`
- `src/pixelscope/ui/iqa_p5f_diagnostics.py`
- `src/pixelscope/ui/iqa_submission_lifecycle.py`
- `src/pixelscope/ui/iqa_result_mapping.py`
- `src/pixelscope/ui/iqa_scene_inspection.py`
- `src/pixelscope/ui/iqa_scene_inspection_lifecycle.py`
- `src/pixelscope/ui/iqa_historical_results.py`
- `src/pixelscope/ui/iqa_historical_results_lifecycle.py`

## Known wrapper chains

Several targets are wrapped repeatedly by independently installed features. Restore order is therefore part of the correctness contract.

```text
MainWindow._render_selection
base -> DifferenceCuration -> QuickCompare -> Issue77UiDesignFollowup

MainWindow._select_document_ids / _remove_document_ids
base -> ReviewSelection -> IqaSceneInspection

MainWindow._update_action_states
base -> DifferenceCuration -> NativeYuvSemantics

MainWindow._register_input
base -> RawInputCompatibility -> FolderDisplayTags

MainWindow._confirm_raw_profile
base -> RawInputCompatibility -> NativeYuvSemantics

MainWindow._difference_result_matches_current_pair
base -> DifferenceCuration -> NativeYuvDifference

MainWindow._update_comparison_page_controls
base -> WorkflowPolish -> BetaWorkspaceHardening

ReviewSelectionController._sync_controls
base -> WorkflowPolish -> BetaWorkspaceHardening

MultiCompareView._prepare_viewers_for_documents
base -> MultiViewReorder -> QuickCompare

RemoteIqaController._track_worker
base -> SubmissionLifecycle -> ResultMapping

RemoteIqaController.settings_changed
base -> ResultMapping -> SceneInspectionLifecycle -> HistoricalLifecycle

IqaWorkspaceController.open_result / shutdown
base -> IqaSceneInspection -> HistoricalIqaResults
```

## Design direction

The authoritative install order already exists in `pixelscope.app.application._compose_main_window_presentation()` and `_compose_remote_iqa()`.

The first shared primitive is therefore a window-owned **composition teardown stack**, not an eager global unpatch operation. Each migrated feature owner registers a teardown callback in installation order. On `QEvent.Close`, the stack invokes those owners in strict reverse order. Each owner is responsible for its own feature cleanup first and then restoring the instance methods it installed.

This distinction matters because some wrapped methods are themselves shutdown paths. Restoring every patched method before feature cleanup could bypass existing cleanup logic. For example, `IqaWorkspaceController.shutdown` is wrapped by Scene Inspection and Historical Results layers.

The teardown stack holds feature owners only through weak references and resolves the callback at shutdown time. It must not create a second bound-method cycle of its own.

Required properties:

1. Feature teardown runs in global reverse installation order.
2. Each owner performs feature-specific cancel/disconnect/quiesce work before restoring its own patches when required.
3. Restoration is idempotent.
4. Teardown runs on the GUI thread, before Qt object destruction / Python cyclic GC becomes cleanup authority.
5. Teardown registration itself must not keep a feature owner alive; the shared stack uses weak owners rather than retained bound callbacks.
6. Persistent patch owners must restore the exact layer they replaced. For class-defined methods that had no prior instance override, teardown should ultimately remove the instance override rather than leave a bound method stored on the instance.
7. Temporary `try/finally` monkey-patches used only inside one synchronous call are not converted unnecessarily.
8. Existing worker cancel/quiescence and signal-disconnect responsibilities remain intact; method restoration does not replace them.
9. No `gc.disable()`, blanket `gc.collect()`, arbitrary sleeps, timeout inflation, or global-pool masking is accepted as a fix.

A more generic runtime patch helper may be introduced later if it reduces per-owner boilerplate, but global teardown ordering remains authoritative through the composition stack.

## Work sequence

Each work item is closed only after implementation review and focused validation.

### WP-0 — Inventory and reproducer baseline

- [x] Port the static monkey-patch inventory audit from forensic PR #88.
- [x] Port the opt-in A -> B Qt lifecycle reproducer from forensic PR #88.
- [ ] Run the audit on the implementation branch and reconcile all candidates with this plan.
- [ ] Record baseline reproducer frequency on Windows.

### WP-1 — Central LIFO composition lifecycle

- [x] Add the weak-owner composition teardown stack.
- [x] Install it at the start of production MainWindow composition.
- [x] Add focused UI tests for LIFO ordering, idempotence, callback validation, and failure isolation.
- [ ] Validate the new lifecycle tests locally on the pinned Windows/PySide environment.
- [ ] Register the first real production patch owner and prove reverse-order cleanup through production composition.

### WP-2 — High-risk IQA patch chains

- [ ] `IqaSceneInspectionController` mutation boundaries.
- [ ] `IqaSceneInspectionLifecycle`.
- [ ] `HistoricalIqaResultsController` / lifecycle.
- [ ] Remote IQA settings/submission/result-mapping/diagnostics patch sites.
- [ ] Verify existing IQA shutdown semantics remain intact.

### WP-3 — MainWindow selection / Difference / registration chains

- [ ] ReviewSelection / DifferenceCuration.
- [ ] QuickCompare / Issue77 follow-up / MultiViewReorder.
- [ ] RAW/YUV compatibility and Difference/runtime contracts.
- [ ] FolderDisplayTags / RecentEntries.

### WP-4 — Presentation / workspace patch sites

- [ ] WorkflowPolish method replacements.
- [ ] BetaWorkspaceHardening wrappers.
- [ ] Remote settings/presentation wrappers not already covered.

### WP-5 — Guardrail and durable contract

- [ ] Static/architecture check rejects new persistent instance monkey-patches that bypass a registered lifecycle owner / restore contract.
- [ ] `docs/QUALITY.md` explicitly documents runtime monkey-patch cycle and LIFO restoration requirements.
- [ ] Update relevant architecture/harness documentation if implementation introduces a shared lifecycle primitive.

### WP-6 — Validation

- [ ] Focused regression tests for each migrated owner.
- [ ] A -> B reproducer repeated without native crash/hang under normal automatic GC.
- [ ] Existing Issue #81 lifecycle stress tests pass.
- [ ] Full Windows pytest suite repeated in fresh processes.
- [ ] Ruff / format / mypy / docs checks pass.
- [ ] Independent review finds no lifecycle or ordering blocker.

## Acceptance

This work is not complete merely because one reproducer stops failing. Completion requires the persistent monkey-patch inventory to be reconciled, deterministic GUI-thread LIFO teardown to cover every relevant production site, each migrated owner to restore its own runtime method layer without skipping feature cleanup, no observable feature regression, and repeated full-suite validation under normal Python GC.
