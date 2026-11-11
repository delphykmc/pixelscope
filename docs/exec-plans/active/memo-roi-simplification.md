# ROI Memo simplification

Status: Implementation finished; known native validation failures and owner/review acceptance pending.

**November 12 checkpoint supersedes the Draft/validation gates below:** independent
source review accepted `5cc63835` after the destination-revision race fix. The
fixed-head normal-GC Windows full run passed **1,918 tests, 1 warning in 447.33s**.
Historical failure investigation and physical owner acceptance remain distinct;
merge tracking and follow-up are in [the November 12 record](issue-210-review-merge-followup.md).
Owner: ChatGPT-assisted, 2026-11-09.
Branch/PR: `codex/memo-evidence-cleanup-20261109`, #227.

## User contract

Memo is one current image-comparison context with a list of ROI records, never a
catalog of files. Changing selected images or their order clears the in-memory
notebook without searching or restoring old notes. Open Memo is the explicit way
to revisit saved work. Memo-to-viewer navigation remains one-way.

A new manually drawn ROI gets a blank note and a new ROI record. Selecting a list
entry shows its note and ROI. Title/note edits immediately update memory; Save Memo
persists them. Unsaved changes use an amber marker; saved state uses a green marker.
The ROI list supports adding/removing entries. No Update or separate Export commands.
Save Memo retains crops and optional native CSV data; originals are not embedded.

## Implementation and invariants

- Stable MainWindow ROI/source signals, no runtime method replacement. Observe
  manual ROI gestures separately from programmatic restoration.
- File-selection reset cancels capture/restore epochs, clears rows/editor/crops and
  detaches the previous save path. Returning to the old files does not match keys.
- Loading a Memo and its own restoration cannot clear that same document.
- Text widget population is signal-blocked; typing edits text, never historical crops.
- Preserve bounded worker I/O, source verification and existing native authorities.
- Existing untracked owner diagnostics and initial visual guide are preserved.

## Validation

New actual Qt workflow regression covers two ROI records, immediate text edits,
save/reopen, original ROI navigation, order-change reset, no reverse matching,
and deletion. Update earlier tests whose multi-file accumulation or Export UI
contracts were explicitly retired; retain native RAW/YUV and offline evidence checks.
Run focused tests, Ruff, mypy, docs and required Windows regression checks. Earlier
full-suite clipboard/RAW dialog failures remain recorded in the previous plan.

## Progress

- Source and UI signals implemented; first new Qt workflow test passed (1 in 2.94s).
- Separate Export UI, source browsing/profile-dialog UI, hidden Tags widget and
  standalone ROI-export backend were removed. PNG encoding is now a small
  `io/memo_images.py` helper for immutable captures, preserving Gray/RGB/RGBA,
  noncontiguous input and exact bounds.
- Save includes `index.html` in the same archive with validated PNG/CSV assets.
  Older archives without HTML remain readable. HTML regeneration is validated on
  read; source paths remain only in the private record, not the report.
- Automatic ROI creation observes completed manual gestures while Memo is visible.
  Hidden Memo performs no hash/crop work; reopening starts a blank record for an
  intervening ROI gesture. Text input waits for capture, preventing unbound edits.
  Optional Statistics waits on the existing analysis worker's completion signal;
  no polling timer, extra calculation or reverse file matching is introduced.
- Context reset revokes capture/restore and late Open/Save callbacks cannot replace
  the new context or carry the old save path into it. Memo's own verified restore
  publication is distinguished from a new user selection through the owned adapter.
- Current ROI list and editor are temporary. No discard modal is required at
  context change or close; an ongoing file operation completes before close.
- Existing native restart test now verifies 2/4/6-source context resets and reopens
  the last ROI. Native input approval is through File, with no Memo file chooser.
  Obsolete Export UI tests were removed; their crop integrity/bounds coverage is
  retained in the new image and archive tests.

## Observed validation before full run

CPython 3.10.11 / PySide6 6.4.2, Windows normal automatic GC:

- Applicable Memo/archive/native/retirement/Difference selection:
  **87 passed in 25.83s**. Last empty-notebook Saved-marker refinement was then
  covered by the ROI workflow tests: **2 passed in 3.87s**.
- Latest actual Qt screenshot capture: **1 passed in 3.38s**. The main view,
  unsaved ROI panel and saved green marker were visually inspected. This is agent
  inspection of synthetic inputs on the available display, not owner acceptance.
- Source mypy: **132 files, no issues**. Tracked Ruff lint/format plus new files:
  **402 files formatted**, lint clean. Docs contract passed; strict MkDocs exit 0;
  pip check found no broken requirements; diff whitespace check clean.
- Full test command will run after committing this source, because the inherited
  Sandbox preflight rejects uncommitted production inputs. Earlier baseline
  clipboard/RAW geometry failures are recorded in
  [the preceding integration record](memo-evidence-cleanup.md), not called fixed.
- Guide: [current screenshots and numbered steps](../../ui/memo-visual-guide/README.md).
  The requested 1400x880 window is constrained by this test display; screenshots
  show the actual available geometry. No physical DPI/monitor/SMB or private
  Enterprise acceptance is claimed. No dependencies or packaging tools changed.

## Remaining gates

Resolve/recheck native full-suite failures, independent final-code review and owner workflow
acceptance. Single View Statistics requires only that image selected; Multi View
captures page Statistics. RAW/YUV originals need existing approved input settings.
The inherited native decode budget is 128 MiB. Existing owner untracked diagnostic,
packaging and fixture files are untouched. MAIN remains unmerged; #227 stays Draft.

## Changed files in this revision

- `docs/ARCHITECTURE.md` (M)
- `docs/CURRENT_STATE.md` (M)
- `docs/PRODUCT_SPEC.md` (M)
- `docs/exec-plans/active/memo-roi-simplification.md` (A)
- `docs/ui/memo-visual-guide/01-main.png` (A)
- `docs/ui/memo-visual-guide/02-memo.png` (A)
- `docs/ui/memo-visual-guide/03-memo-panel.png` (A)
- `docs/ui/memo-visual-guide/04-memo-saved.png` (A)
- `docs/ui/memo-visual-guide/README.md` (A)
- `docs/user-guide/workflows/review-findings.md` (M)
- `src/pixelscope/app/main_window.py` (M)
- `src/pixelscope/io/memo_archive.py` (M)
- `src/pixelscope/io/memo_images.py` (A)
- `src/pixelscope/io/memo_roi_export.py` (D)
- `src/pixelscope/ui/comparison_analysis_panel.py` (M)
- `src/pixelscope/ui/review_capture_adapter.py` (M)
- `src/pixelscope/ui/review_main_window_adapter.py` (M)
- `src/pixelscope/ui/review_panel.py` (M)
- `src/pixelscope/ui/review_window_integration.py` (M)
- `tests/ui/test_memo_evidence.py` (M)
- `tests/ui/test_memo_roi_workflow.py` (A)
- `tests/ui/test_w09b_named_findings_roundtrip.py` (M)
- `tests/ui/test_w09b_production_wiring.py` (M)
- `tests/unit/test_memo_archive.py` (M)
- `tests/unit/test_memo_images.py` (A)
- `tests/unit/test_memo_roi_export.py` (D)

## Reproduction commands

From repository root with CPython 3.10 virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_memo_archive.py tests/unit/test_memo_images.py tests/unit/test_w09a_review_repository.py tests/unit/test_w09b_review_workflow.py tests/unit/test_w09b_review_guards.py tests/unit/test_w09b_native_decoder.py tests/ui/test_memo_roi_workflow.py tests/ui/test_memo_evidence.py tests/ui/test_w09b_production_wiring.py tests/ui/test_w09b_named_findings_roundtrip.py tests/ui/test_retired_w05_w06.py tests/ui/test_toolbar_cleanup.py tests/ui/test_p4a_difference_curation.py
.\.venv\Scripts\python.exe scripts/check_docs.py
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m mkdocs build --strict
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Hosted full pytest is not added. Source/test changes require normal-GC local Windows
validation; existing unrelated native failures are reported rather than masked.

## Final committed-source result

Tested source/test SHA: `d7d319cb1df71c11534eaaf9f882d9af4fb7900e`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short --junitxml=temp/memo-roi-full-20261109.xml
```

Observed **11 failed, 1906 passed, 1 warning in 465.00s**, exit 1. All current
Memo-specific tests passed. Failures are the same families reproduced previously
on pristine MAIN `98d2a603`: nine clipboard operations with COM OpenClipboard
`0x800401d0`, RAW dialog compact-height timeout, and Difference RGB geometry parity.
The latter was intermittent in the preceding full runs; it is not claimed fixed.
The warning is the existing intentional duplicate-ZIP tamper test. Assertions,
timeouts, GC and native clipboard behavior were not weakened or suppressed.

The latest code also covers editing/dirty marker after saving deletion of every ROI,
waiting for optional Statistics without another command, hidden Memo deferred work,
and stale Open results after file reset. No reverse file discovery or key matching
was added. Full validation is **not clean**; this remains a Draft with no MAIN merge.

Commits use owner-configured Git identity and
`Co-authored-by: ChatGPT <noreply@openai.com>`; PR/issue updates are marked
ChatGPT-assisted. All eleven original untracked owner files are preserved. Final
follow-up records only validation documentation, with source/test trees unchanged.
