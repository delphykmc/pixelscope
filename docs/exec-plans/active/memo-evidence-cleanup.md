# Memo evidence and preset cleanup

Status: Implementation complete; validation limitations and owner/review acceptance pending
Owner: ChatGPT-assisted implementation for owner request of 2026-11-09
Branch: `codex/memo-evidence-cleanup-20261109`

## Goal and scope

During comparison, draw an ROI and add a note. Each note freezes per-source
8-bit PNG crops and, when explicitly requested, already-presented native ROI
Statistics. Save one editable `.pxmemo`; reopen notes and crops without originals,
or verify/reopen the original images at the saved ROI when available. Export
offline HTML with reusable PNG/CSV files from the saved evidence, never recrop
at save/export time. Session remains the full working-environment workflow.

Retire redundant W05/W06 preset engines, retaining canonical source selection,
2/4/6 comparison, Difference, zoom, Sync and native dock persistence/reset.
No new workspace mode, forced IQA docking, decoder changes, packaging or dependency.

## Baseline and consolidation

- Start: W09b #222 `56104982`, MAIN `98d2a603`.
- Reuse actual W05/W06 retirement implementation from #224. #223 duplicates its
  retirement goal but contains only a checkpoint. Preserve W09b shutdown wiring.
- Reuse #226 `memo_archive.py` and regression foundation because it embeds the
  existing validated ReviewDocumentV1. Do not introduce #225's parallel region
  identity model or either proposal's forced Dock arrangement.
- Existing ReviewLibrary/source attestation/W04 restore remain authorities;
  `.pxreview` remains readable as legacy metadata-only input.
- Existing untracked owner files are excluded from edits/commits.

## Invariants and design

1. ROI images freeze at Add, in the existing bounded capture worker, with the
   same GUI/source generation fence as the note. No live widgets in new worker data.
2. Text edits do not replace crops. Delete removes only the selected entry/assets.
3. Optional Statistics copy only matching current/presented native ROI evidence;
   no implicit calculation or preview-RGB numerical authority.
4. Archive I/O and HTML export use bounded workers; failed/corrupt opens preserve
   the existing notebook. Dirty revisions and concurrent edits cannot be marked saved.
5. Missing/changed originals leave stored evidence readable without changing the
   live viewer or silently binding historical evidence to replacement images.
6. HTML omits automatic original paths and includes only relative PNG/CSV assets;
   user-authored note/title text is explicitly included.
7. CPython 3.10; normal GC; deterministic shutdown; native/Qt tests stay local.

## Slices and validation

1. Integrate retirement and remove hide-only compatibility code; regression on
   original layouts, Difference, source pages and Qt dock persistence.
2. Harden one archive implementation; roundtrip, corrupt/oversized input,
   immutable crops, optional CSV, offline report, collision/revision checks.
3. Capture/UI integration; thumbnail evidence, optional stats, save/open/report,
   missing originals, text edit/delete, save races and late callbacks.
4. Update Product Spec, Architecture, current-state entry and owning User Guide.
5. Focused unit/UI checks, Ruff/docs/mypy/pip/diff, full Windows normal-GC pytest;
   inspect durable-doc deletion scope and actual rendered UI before completion.

## Progress

- 2026-11-09: Inspected #222-#226 and source/tests. Created separate integration
  branch; integrating #224 and selecting #226's existing-record archive foundation.
  No completion or test PASS claimed at this checkpoint.
- Implemented one archive/capture/UI path, removed unused preset pair seam and
  hide-only toolbar module, added Memo to Help navigation. Source and native
  numerical authorities remain unchanged. Archive writes use sibling lock and
  revision/document identity checks; offline HTML contains reusable PNG/CSV assets.
- Observed CPython 3.10.11 / PySide6 6.4.2 Windows focused checks:
  - `python -m pytest -q tests/unit/test_memo_archive.py tests/ui/test_memo_evidence.py`:
    **14 passed in 5.79s** after final CSV/button changes.
  - Memo/retirement/guards/Difference curation selection: **30 passed in 9.52s**.
  - Memo evidence and original RGB/RAW/YUV native restore tests:
    **10 passed in 17.99s** before the final CSV/button-only changes.
  - Source mypy **132 files**, tracked Ruff format **401 files**, tracked Ruff lint,
    docs contract, strict MkDocs and pip check passed in the observed runs.
- Automated real-Qt screenshot inspected at available **1029 x 775** pixels
  (requested window 1400 x 880 was constrained by this display). Corrected an
  orphan legacy Tags field, enabled Locate image for offline notes, enlarged
  tiny saved-crop thumbnails and shortened report action. This is agent visual
  inspection, not owner/hardware DPI or independent UX acceptance.
- Sandboxed hard-link tests failed WinError 5; the same focused contracts passed
  with ordinary Windows access. Initial full pytest was interrupted after existing
  Sandbox preflight rejected uncommitted production inputs; it is NOT a full PASS.
  Commit final implementation before rerunning that SHA-sensitive full gate.
- `ruff check .` finds four existing lint errors in untracked owner GC diagnostics;
  `ruff format --check .` identifies those three scripts. They are left untouched.
  Tracked-file checks exclude these pre-existing untracked diagnostics.
- Full Windows run at `b8027743`: `python -m pytest -q` completed with
  **11 failed, 1904 passed, 1 warning in 452.26s**, exit 1. Nine failures involve
  native clipboard operations (COM OpenClipboard `0x800401d0` / empty clipboard);
  the remaining failures are Difference geometry parity and RAW dialog height.
  Detached pristine MAIN `98d2a603` reproduced both Difference parameter failures,
  the RAW height timeout and both clipboard-support failures (**5 failed in
  9.19s**). Assertions/timeouts/clipboard paths were not weakened or suppressed.
- Post-run workflow review found Single View with several Selected sources tried
  to capture hidden Multi View geometry. Added visible-original-only capture with
  exact Single viewport; Selected and Primary remain unchanged. A regression
  reproduced `layout-not-settled` before correction and passes after correction.
  Optional Statistics for a single canvas with several Selected sources requires
  Multi View or selecting only that image, rather than copying unrelated rows.
- Final applicable selection after the Single View correction: `python -m pytest -q`
  over Memo archive/ROI export, W09a repository, W09b workflow/guards/native decoder,
  Memo evidence, production RGB/RAW/YUV restore, retirement/toolbar and P4-A
  Difference curation modules: **86 passed in 25.91s**. Docs, tracked Ruff lint/format
  (**401 files**) and mypy (**132 files**) passed again. The corrected source is
  committed before its final full normal-GC run; no full PASS is inferred.

## Remaining acceptance

Resolve/recheck remaining native Windows full-suite failures; final exact-code review;
owner interaction on actual comparison images and physical DPI/multimonitor/SMB.
RAW/YUV reopen may require explicit native-profile approval. Legacy notes without
crops cannot gain historical pixels by conversion. Source/profile verification
still has its inherited 128 MiB native decode input budget. No private Enterprise
source or packaging tools are required or executed. No merge or deployment claimed.

## Final observed checkpoint (2026-11-09)

- Tested final source/test SHA: `a25a64b57cd294c568bc329ac959a73d68149617`.
- `python -m pytest -q --tb=short --junitxml=temp/memo-final-full-20261109.xml`:
  **10 failed, 1906 passed, 1 warning in 449.91s**, exit 1. Nine clipboard failures
  show COM OpenClipboard `0x800401d0`; one RAW dialog compact-height assertion times
  out. These failure families reproduce on pristine MAIN. The earlier Difference
  parity failure did not recur in this full run; it is not claimed fixed.
- The duplicate-ZIP warning is from the existing intentional tamper test. No GC,
  assertions, test skips, timeouts, clipboard behavior or numerical rules changed
  to disguise native failures. Full validation is **not clean**.
- `python scripts/check_docs.py`: **Documentation contract passed**.
- `python -m mkdocs build --strict`: exit **0**, built offline Help; existing vendor
  README not in nav is informational. `python -m mypy src`: **132 files, no issues**.
- Tracked Python files via `git ls-files '*.py'`: `python -m ruff check` exit **0**;
  `python -m ruff format --check`: **401 files already formatted**.
- `python -m pip check`: **No broken requirements found**. `git diff --check`: clean.
- `python -c "import pixelscope; print(pixelscope.__file__)"` confirms this checkout's
  `src/pixelscope/__init__.py`, not an unrelated editable installation.
- Draft **#227** is the single implementation PR. #222–#226 were closed without
  merging and point to it; branches/reviews are retained. Issue #210's original
  plan is retained with the current product direction taking precedence.
- Commits use owner-configured identity with
  `Co-authored-by: ChatGPT <noreply@openai.com>`; GitHub PR/issue updates are marked
  ChatGPT-assisted. No separate messages/comments to people were sent.
- Agent reviewed real-Qt screenshots. Owner manual workflow, independent code/UX
  review, physical DPI/multimonitor/SMB and private Enterprise acceptance remain
  unperformed. Existing owner untracked files and MAIN are unchanged.

Exact applicable test selection (86 passed in 25.91s); commands use
`.\.venv\Scripts\python.exe` from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_memo_archive.py tests/unit/test_memo_roi_export.py tests/unit/test_w09a_review_repository.py tests/unit/test_w09b_review_workflow.py tests/unit/test_w09b_review_guards.py tests/unit/test_w09b_native_decoder.py tests/ui/test_memo_evidence.py tests/ui/test_w09b_production_wiring.py tests/ui/test_w09b_named_findings_roundtrip.py tests/ui/test_retired_w05_w06.py tests/ui/test_toolbar_cleanup.py tests/ui/test_p4a_difference_curation.py
```

## Changed files

Relative to starting W09b `56104982` (the PR also includes that earlier W09b work):

- `docs/ARCHITECTURE.md` (modified)
- `docs/CURRENT_STATE.md` (modified)
- `docs/PRODUCT_SPEC.md` (modified)
- `docs/exec-plans/active/issue-210-preset-retirement.md` (added)
- `docs/exec-plans/active/memo-evidence-cleanup.md` (added)
- `docs/user-guide/features/files-workspace.md` (modified)
- `docs/user-guide/features/plots-workspace.md` (modified)
- `docs/user-guide/index.md` (modified)
- `docs/user-guide/llms.txt` (modified)
- `docs/user-guide/workflows/compare-images.md` (modified)
- `docs/user-guide/workflows/review-findings.md` (modified)
- `mkdocs.yml` (modified)
- `src/pixelscope/app/bootstrap.py` (modified)
- `src/pixelscope/app/main_window.py` (modified)
- `src/pixelscope/core/comparison_presets.py` (removed)
- `src/pixelscope/io/memo_archive.py` (added)
- `src/pixelscope/ui/beta_workspace_hardening.py` (modified)
- `src/pixelscope/ui/difference_curation_lifecycle.py` (modified)
- `src/pixelscope/ui/presentation_controls.py` (modified)
- `src/pixelscope/ui/preset_view_state.py` (removed)
- `src/pixelscope/ui/quick_compare.py` (modified)
- `src/pixelscope/ui/review_capture_adapter.py` (modified)
- `src/pixelscope/ui/review_panel.py` (modified)
- `src/pixelscope/ui/review_window_integration.py` (modified)
- `src/pixelscope/ui/toolbar_cleanup.py` (removed)
- `src/pixelscope/ui/workspace_presets.py` (removed)
- `tests/ui/test_memo_evidence.py` (added)
- `tests/ui/test_retired_w05_w06.py` (added)
- `tests/ui/test_toolbar_cleanup.py` (modified)
- `tests/ui/test_w05_comparison_presets.py` (removed)
- `tests/ui/test_w06_workspace_presets.py` (removed)
- `tests/ui/test_w09b_named_findings_roundtrip.py` (modified)
- `tests/ui/test_w09b_production_wiring.py` (modified)
- `tests/unit/test_comparison_presets_contract.py` (removed)
- `tests/unit/test_memo_archive.py` (added)
