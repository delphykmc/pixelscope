# Memo Viewer and report convenience

Status: Implementation and full Windows validation complete; merge tracked in PR #228.
Owner: ChatGPT-assisted, 2026-11-12.
Branch/PR: `codex/memo-viewer-report-20261112`, #228.

## Authorized behavior

- Display every current Memo ROI as a clean rectangle with a top-left numbered
  label in matching original viewers; selected ROI is emphasized. These are
  passive decorations, not additional editable analysis ROI authorities.
- Retain one Save Memo action. The editable `.pxmemo` remains canonical; also
  generate a same-basename `_report` folder containing immediately usable HTML,
  annotated PNGs and optional CSVs. No extra Export mode or file catalog.
- Suggest a Windows-safe basename from the first source and local timestamp.
- Put base filename and x/y/width/height in report captions and a PNG footer;
  preserve the exact recorded crop separately inside `.pxmemo`.

## Invariants

No source matching, selection-reset, Session, numerical analysis or original
pixels change. Never bind historical overlays to unrelated/unverified sources.
Use owned graphics items with deterministic teardown; no monkey-patching, polling
or heavy GUI-thread I/O. Retain old archive HTML compatibility. A report is derived
from the frozen snapshot, not a fresh capture. Generated folders must not overwrite
unrelated directories or edited report files. Archive save and report publication
are separate filesystem transactions; report failure must explicitly report that
the notebook saved, preserve its revision and allow another Save to retry.

## Implementation and checks

1. Owned passive Viewer decoration and coordinator publication/reset/restore tests.
2. Default save suggestion, annotated report images and managed report publication
   with filename/path/overwrite/failure tests; expose report location after save.
3. Narrow user-guide/product/architecture updates, actual UI/report screenshots,
   focused UI/archive tests and broad cheap gates. Run the local normal-GC full
   suite for merge readiness; do not add full pytest CI.

Existing uncommitted two-file eleven-failure verification record and eleven owner
untracked files are preserved. No sleep or automation is reinstated.

## Progress

Baseline: HTML/PNG/CSV were embedded inside the ZIP only, the chooser had no
suggested name, and Viewer owned only one editable analysis ROI.

Implemented owned passive rectangles/labels with verified capture/restore
bindings, selection emphasis and context reset/teardown. Source replacement
clears decorations. Mode changes republish matching original views without
changing the active analysis ROI or Fit bounds. No matching/scanning is added.

Save suggests `Memo_<first-source>_YYYYMMDD_HHMMSS.pxmemo` and writes a sibling
`<name>_report/`. Frozen canonical crops remain in the archive; report PNGs have
a separate metadata footer and text metadata. HTML captions give the base filename
and x/y/width/height; report image names carry the same data. Old generated HTML
is still strictly validated and readable. The managed folder refuses edited or
foreign files, checks reparse points, stages publication and rolls back a failed
install. Report-only failure preserves the saved notebook revision and is reported
explicitly, so another Save does not mistake the notebook for an external edit.

Initial focused archive/report tests: 20 passed in 2.08s. After adding UI tests,
the pinned PySide6 format-argument mismatch was reproduced and corrected using
format autodetection plus QImageWriter/QByteArray. UI report/ROI tests then passed
6 in 6.00s. Mypy passed 134 files. Expanded validation, docs and visual checks are
still pending; no overall completion or merge is claimed.

Expanded Memo/restore/retirement/Difference selection passed **101 in 29.91s**.
Subsequent focused footer/link/partial-save tests and screenshot capture passed
**30 in 9.38s**; final targeted error/retry tests passed **18 in 7.90s**. Managed
folder checks now also protect nested marker names, added empty directories and
edits/corrupt ownership records occurring after the old folder is moved. That
final report/screenshot selection passed **13 in 4.00s**. Ordinary rendering
exceptions return an explicit report-only failure after the notebook commit.

Inspected actual screenshots `docs/ui/memo-visual-guide/05-roi-overlays.png` and
`06-crop-metadata.png`: three labeled ROIs appear in both original viewers, and
the footer includes the base name and all four coordinates without drawing over
the crop. The last capture waits for native analysis presentation to settle.
The status uses the existing space for a safe Open report link and folder name;
ordinary status/error text remains plain text. This is synthetic-data visual QA,
not physical DPI/multimonitor/SMB/packaged/Enterprise or owner acceptance.

Product, architecture, user-guide and numbered visual-guide changes preserve the
merged documentation baseline. Earlier local eleven-failure completion records
are included unchanged in intent; that completed investigation is not reopened.
No dependencies, packaging tools, timers or automations are added.

## Final validation checkpoint

Tested source/test head: `785659db4370acb2682df194825a14761b0b9aec`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short --junitxml=temp/memo-feedback-full-20261112.xml
```

Observed **1936 passed, 1 warning in 450.57s**, exit 0, normal automatic Windows
GC. No source or HEAD changes occurred during the run. The single warning is
the existing intentional duplicate-ZIP-member tamper test. No skipped tests,
weakened assertions, timeouts or tolerance changes are introduced.

Independent read-only reviewer `/root/independent_memo_review` found no actionable
code finding and separately observed archive/report **25 passed in 2.13s**, docs
contract and merge-base diff check clean. Source-head CI checks completed with
success; focused Windows CI was skipped by scope classification, not represented
as a pass. Full pytest remains a local gate only. The final documentation-only
commit retains this exact source/test tree; final acceptance/merge is on PR #228.

Other observed commands and results:

- Tracked `ruff check` / `ruff format --check`: **406 files**, clean.
- `python -m mypy src`: **134 source files**, no issues.
- `python scripts/check_docs.py`: documentation contract passed.
- `python -m mkdocs build --strict`: exit 0.
- `python -m pip check`: no broken requirements.
- `git diff --check`: clean. Durable docs show narrow additive changes; inherited
  contracts are preserved and earlier validation notes remain dated history.

### Changed files

- `src/pixelscope/app/main_window.py`: republish passive marks after canonical rendering.
- `src/pixelscope/io/memo_archive.py`: explicit captions and strict old/new HTML validation.
- `src/pixelscope/io/memo_report.py`: suggested names and managed report publication.
- `src/pixelscope/ui/image_viewer.py`: owned passive rectangles/labels and teardown.
- `src/pixelscope/ui/memo_report_images.py`: worker-rendered metadata footer PNGs.
- `src/pixelscope/ui/review_main_window_adapter.py`: verified binding snapshot.
- `src/pixelscope/ui/review_panel.py`: safe report link in the existing status area.
- `src/pixelscope/ui/review_window_integration.py`: publication and single-save orchestration.
- `tests/ui/test_memo_evidence.py`, `test_memo_roi_workflow.py`,
  `test_memo_report_images.py`: UI, context, image, error/retry and ownership contracts.
- `tests/unit/test_memo_archive.py`, `test_memo_report.py`: old HTML, naming,
  ready-to-use folder, protected edits/directories and rollback tests.
- `docs/ARCHITECTURE.md`, `CURRENT_STATE.md`, `PRODUCT_SPEC.md`,
  `user-guide/workflows/review-findings.md`: narrow contract updates.
- This plan and `docs/ui/memo-visual-guide/README.md`, `05-roi-overlays.png`,
  `06-crop-metadata.png`: progress, evidence and numbered actual-screen guide.
- `docs/exec-plans/active/issue-210-review-merge-followup.md`: preserve the earlier
  authorized eleven-failure completion record; that investigation stays complete.

### Limits and attribution

Manual/visual evidence is inspection of actual Qt screenshots and generated PNGs
using synthetic images; no new human owner, physical DPI/multimonitor, SMB,
packaged execution or private Enterprise acceptance is claimed. Decorations are
bound to matching verified original viewers; derived images are not assigned
historical source identity. Folder and archive are separate transactions with
explicit partial-save status. Non-cooperating filesystem writes after the last
check remain an external race limitation, as with the existing archive writer.

Agent commits use configured `mc.kang` identity plus
`Co-authored-by: ChatGPT <noreply@openai.com>`. GitHub activity is marked
ChatGPT-assisted; no human commits are rewritten. Existing eleven owner untracked
files are excluded from commits. Issue #210 remains open. Power timers stay
cancelled and the old continuation stays PAUSED. MAIN merge is not claimed by
this pre-merge documentation checkpoint.
