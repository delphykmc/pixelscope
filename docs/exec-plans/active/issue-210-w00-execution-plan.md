# Issue #210 W00 — execution plan, ownership and implementation delegation cards

Status: **design PR / independent review pending; no implementation authorization implied**.
Pinned baseline `main@473af64b0b40905683594d218470ca194d81242c`. Parent https://github.com/delphykmc/pixelscope/issues/210 . Companion: [W00 technical contract](issue-210-w00-technical-contract.md). Authoritative D01–D04 and provisional T01–T08: [policy comment](https://github.com/delphykmc/pixelscope/issues/210#issuecomment-6608504294).

## Dependency DAG and change-control

```text
W00 independent review gate
 ├─ W01 exact physical zoom ─ W04 view-state ─ W05 compare presets ─┐
 ├─ W02 context/snapshot export ──────────────────────────┐         │
 ├─ W03 alias identity ─ W06 layout ─ W07 pivot table       │         │
 │                    └───────────────────────────┐       │         │
 ├─ W08 RAW/YUV profile UX                         │       │         │
 ├─ W11 format demand investigation (CONDITIONAL implementation)
 └─ W12 scene matching investigation (CONDITIONAL implementation)
 W02 + W03 + W04 ─ W09 Review model/restore ─ W10 report (also requires W02 + W03)
 W01..W10 accepted and integrated ─ W13 owner Windows acceptance
```

**Precise gates:** W01/W02/W03/W08 only after W00 reviewed/merged or explicitly approved signed-off immutable design SHA; W04 after W01 geometry APIs; W05 after W04; W06 after W03 presentation adapter; W07 after W03 AND W06 shared layout integration; W09 after W02 snapshot interface + W03 aliases/identity + W04 DTO; W10 after W02 bundle writer + W03 labels + W09 Review schema; W13 after W01–W10 integration, plus explicit W11/W12 disposition. W11/W12 *research* can start with W00 approval; implementation requires their own sample-based reviewed contract, W11 also coordinates W08 when touching YUV input. This strengthens the parent broad DAG by requiring W06 before W07's shared-file edits and W04 before W09.

**Shared integration owner: orchestrator only** for `src/pixelscope/app/main_window.py`, `app/bootstrap.py`, Session v1 schemas, central settings/worker registration, `docs/CURRENT_STATE.md`, `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, `QUALITY.md`, `DECISIONS.md`, and central User Guide navigation. Workers propose minimal typed adapter/signals and report necessary changes without editing these shared files concurrently. No worker touches `src/pixelscope_enterprise/**`, `tests/enterprise/**`, `src/pixelscope_iqa_reference/**` or SUB assets. No silent Git history rewrite; no MAIN commits by implementation agents. Source paths below are relative to `src/pixelscope/`; new files are proposed, confirm existence and actual call-site owner at task start.

### W01–W13 delegation cards

Each card is a concrete task contract. Required footer for *every* implementation agent: “You are not alone in the codebase. Do not revert others' changes; coordinate shared edits. Use isolated `codex/` branch/worktree; no unowned file patches; no MAIN merge. Commit with `Co-authored-by: ChatGPT <noreply@openai.com>`. Deliver exact base/head SHA, changed paths, measured commands/output, manual evidence, risks and draft/ready-for-review PR. Independent read-only reviewer separately reviews exact head SHA.”

| W | Observable deliverable and required dependency | Editable scope / integration lock | Focused tests; critical negative test |
|---|---|---|---|
| W01 | Exact 100/200/400% physical zoom and true label; W00 | `ui/image_viewer.py`, `ui/multi_compare_view.py`; lock “viewer” until W04 | `tests/ui/test_issue75_viewer_coordinates.py`, `test_ui_workspace_contracts.py`; small-image non-clamp, DPR/resize/nonuniform transform |
| W02 | Additive context bundle and immutable analysis capture; W00 | `ui/analysis_export.py`, `io/analysis_export.py`, proposed `io/analysis_bundle.py`, Qt-free DTO; `ui/comparison_analysis_panel.py` export-only seam, then release | `tests/unit/test_analysis_export.py`, `test_analysis_export_metrics.py`, `tests/ui/test_p4e_analysis_export.py`; legacy CSV goldens, pending/stale ROI, collision-after-extension, atomic failure |
| W03 | Unique stable source presentation resolver, reuse folder tags; W00 | `ui/folder_display_tags.py`, `ui/tile_header.py`, proposed `core/source_presentation.py`; no new runtime hook graph | source alias unit/UI tests; four duplicate basenames, Unicode/casefold, tag removal, cache unaffected |
| W04 | Qt-free view DTO + live adapter/restoration; W01 | `ui/multi_compare_view.py`, `ui/image_viewer.py`, proposed `core/review_view_state.py`; viewer lock then release to W05 | W01 spatial suites + page/layout/view regression; unsynced differing centers, late load, missing source, shutdown |
| W05 | Explicit originals 2/4, A/B/Diff, Diff-focus presets; W04 | `ui/difference_curation_lifecycle.py`, `ui/quick_compare.py`, `ui/presentation_controls.py`; shared MainWindow only orchestrator | `test_difference_workspace_contracts.py`, `test_p4a_difference_curation.py`, `test_issue77_wp_c_quick_compare.py`; implicit Calculate forbidden, 6/page/T preserved |
| W06 | Compare/Analyze/Review dock preset, command hierarchy; W03 | `ui/beta_workspace_hardening.py`, `ui/presentation_controls.py`, `ui/responsive_control_layout.py`, `ui/design_tokens.py`; reserve layout controller until W07 | workspace/dock tests; 1400×880, FHD/UHD, DPI, floating/off-screen dock, invalid settings; no selection mutation |
| W07 | Metrics by source pivot and typed units without deleting raw table; W03+W06 | `ui/comparison_analysis_panel.py` (after W02 release), `ui/difference_panel.py`; no W06 concurrent panel patches | `test_plot_statistics_contracts.py`, `test_p1a_files_statistics_header.py`, `tests/unit/test_diff_and_statistics.py`; nonfinite/native YUV+Bayer/delta from unrounded values |
| W08 | RAW/YUV recent/favorite profiles and source interpretation; W00 | `ui/raw_open_dialog.py`, `ui/yuv_open_dialog.py`, `app/raw_input_compatibility.py`, `app/yuv_input_semantics.py`; registration seam orchestrator | `test_p1c_raw_dialog.py`, `test_raw_input_contracts.py`, `test_wp_b_raw_binary_compatibility.py`; invalid stride, sidecar precedence, late preview/cancel |
| W09 | Named findings Review v1 schema/repository then UI/restore; W02+W03+W04 | PR9a: new `core/review_record.py`, `io/review_repository.py`; PR9b: new `ui/review_panel.py` and adapter; MainWindow/Session glue orchestrator | `tests/unit/test_comparison_set.py`, `tests/ui/test_p4c_session_restore.py`, `test_p4c_session_pr33_integration.py` + new strict JSON/transaction/relink tests; future schema/zero sources/late epoch |
| W10 | Static offline HTML/PNG/CSV/JSON report ZIP; W02+W03+W09 | proposed `io/review_report.py`, `core/review_evidence.py`, `ui/analysis_export.py` narrow adapter; reuse W02 ZIP writer | new pure crop/layout/redaction/manifest and small ZIP integration; HTML injection, changed source, full-image private data, interruption |
| W11 | Conditional real-format sample/support matrix first; W00, and W08 coordination before changes | Research doc first; implementation: `io/yuv_profile.py`, `io/yuv_reader.py`, `core/yuv.py`, format-specific tests; separate PR **per chosen format** | Golden NV12/NV21/I420/P010 *only when chosen*; strides/endian/native plane, truncated/odd shapes; retain existing 444/422/420 |
| W12 | Conditional scene-key matching study and exact-match planner; W00 | Research doc first; implementation: `core/folder_navigation.py` or current planner, `ui/document_list.py`; MainWindow adapter orchestrator | `tests/unit/test_folder_navigation_planner.py`, `tests/ui/test_folder_navigation.py`, `test_issue77_wp_b_folder_bootstrap.py`; duplicate key/missing scene/cancel, ordinal unchanged |
| W13 | Owner/local full acceptance and evidence dossier at *integrated exact SHA*; W01–W10 | Tests/manual record and narrow docs updates only; orchestrator owns cross-cutting integration | Full owner/local pytest + static/docs/pip, normal-GC native shutdown, 2/4/6, legacy Session, new Review 3 findings, reports and real DPI; record unrun SMB/human/physical multi-monitor explicitly |

### PR splitting and ownership sequencing

1. W00: documentation-only PR → independent reviewer; no W00 complete until findings resolved and explicit approval.
2. W01, W02, W03 in independent nonoverlapping PRs (W02 and W03 source presentation adapter overlap requires explicit review); W08 optional in parallel with distinct input modules.
3. W04 after W01 viewer integration. W05 after W04. W06 after W03, then W07 after W06 and after W02 releases `comparison_analysis_panel.py`.
4. W09a Qt-free schema/serializer/fingerprint/strict IO, W09b Review UI/transaction/relink; separate review gates and no Session v1 rewrite.
5. W10a evidence crop/native oracle + ZIP, W10b minimal UI integration and offline-render inspection.
6. W11/W12 requirements-only PRs do not include decoder/matching feature flags. Implement format/key only after separate acceptance and review.
7. W13 integration record, no implicit merges or releases. Every PR reports branch, exact base/head, size/additions/deletions, manual status, full narrow test logs and independent reviewer disposition. On divergence re-review new HEAD; old review does not transfer.

## Validation matrix — tests to run, not claimed results

| Domain | Variants / oracle | Owner gate |
|---|---|---|
| Geometry | RGB/Gray, Bayer CFA phase/split, YUV 4:2:0 Y/U/V; Single/2/4/6; Fit vs exact 100/200/400; 100/150/200% Windows per-monitor DPI; 1px checker/impulse, window move across monitors, plots dock/float | W01/W04 owner Windows, physical transform math ≤0.5px pixel-center and ≤0.5% scale proposed |
| Identity | four duplicate basenames, different parent suffix, NFC/casefold collisions, long Korean filename, explicit tag edit/clear, page switch, source reopen/generation | W03 unit/UI; no cache/selection mutation |
| Native analysis | full/ROI, same-sized different-coordinate ROI, gray/RGB/uint16/Bayer/YUV plane sample counts; stat/hist/line/diff channel domain/metric revision | W02/W07/W09 pure+Windows; no preview numerics |
| Difference | A/B ordering, cached/pending/stale, invalid channel, pair changed mid-request, explicit Calculate only, T/slot navigation, page 2, zero active Result | W05/W09; no hidden recalculation |
| Persistence | legacy .pixelscope + comparison-set golden, Review v1 roundtrip, duplicate keys, malformed primitive/future schema, corrupted ZIP, missing/all missing/ambiguous/modified sources, relocation decline | W09 local unit+Windows; no mutation before commit |
| Bundle / privacy | UTF-8/Korean notes, HTML escaping and CSP, exact crop checksum, native YUV/Bayer footprint, manifest entry hashes, no private full path/content, destination overwrite/cancel/unwritable/read-only | W02/W10 pure IO + Windows HTML render |
| Concurrency/lifecycle | stale generation, rapid finding switching, worker completion after close, normal Python GC, idempotent close and overlay teardown, cancel during worker, background SMB delay | W09/W10 owner Windows; no invalid QObject access |
| UX | 1400×880 / 1920×1080 / 3440×1392, DPI100/150/200, Plots dock/float, long labels, 2/4/6, ROI editing, CSV clipboard, RAW/YUV manual interpretation | W06–W08/W13 manual with screenshots and exact steps |

**Proposed executable checks on owner Windows CPython 3.10 venv** (record exit codes and actual counts; do not treat this text as PASS):

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe scripts\check_docs.py
git diff --check
.\.venv\Scripts\python.exe -m pytest -q tests/ui/test_issue75_viewer_coordinates.py tests/ui/test_ui_workspace_contracts.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_analysis_export.py tests/unit/test_analysis_export_metrics.py tests/ui/test_p4e_analysis_export.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_comparison_set.py tests/ui/test_p4c_session_restore.py tests/ui/test_p4c_session_pr33_integration.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m mkdocs build --strict
```

For W00 docs-only gate run `python scripts/check_docs.py`, `git diff --check`, and manually inspect no unexpected deletion; test suite may be marked NOT RUN rather than claimed PASS. In hosted CI never add full pytest; small deterministic non-widget targeted tests only. Windows native tests remain authoritative. For W13 record exact tested repository SHA, test count, OS/Python/Qt/DPR, hardware and observed command transcript; do not silently treat unavailable physical-monitor or SMB tests as passed.

## End-to-end acceptance and release disposition

User workflow: Open 2/4 images → uniquely identify baseline/algorithm targets → Fit↔exact 100% preserving center → choose explicit pair/Calculate → record three distinct named ROI findings → persist `.pxreview` → restart → relink moved sources only after confirmation → restore sources/roles/ROI/view or clearly report unavailable → export offline ZIP with corresponding labeled crops and immutable values. Confirm 6/page, T, legacy `.pixelscope`, native YUV/Bayer math, Display Gain, source reading-only and no private path leakage. W11/W12 independently classified as implemented/approved-deferred with evidence. Capture user task measurements (identification error/re-navigation/re-entry/report edits); any competitive comparison is separately run and not fabricated.

**W00 gate:** technical contract, decision table, risk list and cards exist in this docs PR; independent read-only review of *exact* final SHA and resolution is required before W00 Complete, any implementation authorization or merge. This document does not certify unrun checks.
