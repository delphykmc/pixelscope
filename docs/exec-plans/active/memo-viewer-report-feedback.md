# Memo Viewer and report convenience

Status: Active. Owner: ChatGPT-assisted, 2026-11-12.
Branch: `codex/memo-viewer-report-20261112`.

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

Full normal-GC Windows validation is pending on the next committed source head.
Do not change source or HEAD during that run. Agent commits use the configured
owner identity plus `Co-authored-by: ChatGPT <noreply@openai.com>`. Existing eleven
owner untracked files are excluded from commits. MAIN merge is not claimed.
