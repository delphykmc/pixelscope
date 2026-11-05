# Issue #210 W09b — Draft integration / verification handoff

> **Status: DRAFT, not a completed W09b product.** Source files on branch `codex/w09b-named-finding-native-restore-20261105`. Baseline MAIN `98d2a603d879b7989d21207c7615e5b246d10a4b`. PR #222 must not be merged until end-to-end review/owner acceptance.

## Implemented slices and canonical contracts

| Slice | File | Contract |
| --- | --- | --- |
| Production same-descriptor RAW/YUV decoder | `io/review_native_decoder.py` | `CandidateNativeDecoderV1.decode_signature(CandidateDecodeProbeV1)` never reads from cached Review or preview; W09a double SHA and revision/consent policy remain authoritative. RAW reader MIPI 10/12/14, generic packed, unpacked and YUV Y-first/UV-interleaved plane kernels are reused. W02 `snapshot_source()` provides the signature. |
| Immutable local Finding editor / CAS repository | `core/review_workflow.py` | W09a `ReviewDocumentV1`, `ReviewFindingV1`, `ReviewRepository.load_with_revision()` and `save()`. Never writes Session v1. |
| Named Finding panel | `ui/review_panel.py` | Typed signals only; historical analysis explicitly distinguished from live results. Panel is not yet installed by production bootstrap. |
| Source verification and Restore transaction | `ui/review_restore_controller.py` | Worker `_verify_batch` checks SHA+native signature+per-source consent with bounded input; epoch and late-result filters. A separate `CanonicalReviewRestoreAuthority` supplied by MainWindow owns preflight/commit/retry/cancel. |
| Staged W02/W04 Finding capture | `ui/review_capture_adapter.py` | `capture_review_view_state()`, `capture_presented_analysis()`; file hashes and decoded native samples are attested before a Finding can be persisted. A current/stale mismatch produces `unavailable`, not calculation. |

## Mandatory MainWindow / bootstrap integration ownership

The agent did **not** edit `app/main_window.py` or `app/bootstrap.py`. The orchestrator must add a *narrow typed host seam*, not monkeypatch methods or create a second source registry:

1. Install the `ReviewPanel` in a contribution-owned named dock, add explicit Open/Save actions and a Review Workspace preset affordance, and attach `ReviewLibrary` / `ReviewRestoreController` for the lifespan of the window. Wire Add/Edit/Delete, file pickers and explicit per-candidate profile/relocation approval. The currently supplied panel emits signals only; it is not a user-accessible feature by itself.
2. Produce a persistent runtime `document_id -> ReviewSource UUID` binding for capture. Supply the exact current page, reference and primary authorities, pair/recipe, ROI/line, native channel and display gain. Bind W02 `comparison_analysis_panel.bind_review_source_keys()` only to the canonical binding; do not let a fallback UUID authorize a different file after restart.
3. Submit `attest_staged_finding()` on a bounded worker. Before calling `ReviewLibrary.add()`, recheck every `CaptureSource.still_loaded_as(window.documents)`, epoch, page, role, ROI and selection tokens. Fail closed if source generation changed during attestation. Ensure `ReviewDocumentV1` and private-path consent are valid before invoking repository save.
4. **Read-only preflight:** `CanonicalReviewRestoreAuthority.prepare(RestorePlan)` must validate 100% of exact Finding source keys, generation/profile/geometry, target/primary/reference, ROI, line, channel, layout and profile associations, with zero workspace mutation. Do not register or select anything yet. The saved Review must be valid and all candidates `verified`.
5. **Commit:** `commit(prepared, plan)` must use central registration/selection/page authority. Bind approved profiles through the existing RAW/YUV registration contract. Explicitly suppress/disable implicit Difference Calculate during stage; restore only recipe and pair. The caller owns partial-commit reporting if an image foreground load fails.
6. **Terminal-aware restore:** after real load/display-gain/layout completion, call `MultiCompareView.begin_review_restore(epoch)`, followed by W04 `restore_review_view_state(view, finding.view_state, verified_bindings, epoch=epoch, presentation_mode=...)`. For a pending result, only call `ReviewRestoreController.owner_terminal_notification(epoch)` on **authoritative foreground terminal and settled geometry notifications**, never periodic sleep or a nested event loop. On user interaction, Finding switch, or shutdown revoke epochs and invoke `cancel_review_restore()`.
7. The production UI must expose `applied/pending/unavailable/interrupted` with any partial state; only after end-to-end results are available may Review Workspace preset be considered delivered.

No View/Edit/Source/Session v1 API changes, no automatic relink or disk crawling, no automated Difference calculations, no W10 portable report generation.

## Trust assumptions and remaining risks

- A file with SHA match but mismatched native profile is **unsupported**, never Verified. Same-basename and same-size/mtime are not historical evidence.
- Relocated candidates require **explicit per-Source user confirmation even if SHA matches**; user selects actual file and approved native profile. W09a's verification status is authority. Unverified/missing/changed sources remain offline evidence and must not activate workspace.
- This proof presently applies to application-owned **RAW and YUV with explicit profiles only**. Other image formats, more than the adapter's 128 MiB decode budget, and additional layouts fail closed. This means W09b is NOT yet generally available for RGB PNG/JPEG Findings.
- The current worker decodes in memory (bounded at 128 MiB input); memory expansion and multi-4K full-suite responsiveness require owner measurement. Windows file mutation/SMB locking, normal Python GC, DPI/multimonitor and intermittent COM diagnostics remain unproven.
- Review save/open and the source hash/decoder tests are **unit-level evidence only**. A full start-to-finish UI test of three ROI Findings across restart, profile relink and all W04 restore stages has **NOT RUN**.
- The optional candidate and capture source bindings are not retained in the W09a schema; the orchestrator owns runtime-only maps and must not use local file paths as historic UUID identity.

## Acceptance gates still open

- Real user entrypoint + Review Workspace integration, canonical `MainWindow` staged commit, exact generation checks, profile dialogs and explicit per-source consent.
- Automated Qt workflow and restart+3 Finding selective restore; 2/4/6 sources, Difference, ROI/Line, physical zoom, channel, gain, sync off/on, rapid switch, close/GC.
- Full Windows normal-GC owner suite with exact counts, warnings, exit code; real Windows lock and SMB diagnostics, profile semantic oracles.
- Independent code review on final **exact PR head** and orchestrator merge authorization.

## Validation reporting rules

Use exact SHA per run and never combine count from an older tested source SHA with a later untested HEAD. Temporary focused workflow `.github/workflows/w09b-native-focused.yml` is only a CI aid; remove it before merge or formalize it under owner-approved CI policy. Tests and static checks may continue evolving on this Draft PR.
