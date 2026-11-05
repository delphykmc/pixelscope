# PixelScope Memo V2 — multi-ROI notebook, embedded crops and offline HTML

Status: **Draft implementation contract / follow-up to W09b #222** (2026-11-06).
Parent: Issue #210. Starting code SHA: `561049821e7f55152bd4168419d3265c16c113dd`.
This work is separate from W05/W06 retirement PR #223 and does NOT add a
Workspace Layout preset/menu.

## Product decision

Memo is **an inspection notebook**, not a Save Session replacement, a generic
workspace layout, or an IQA measurement owner. A user can mark many ROIs on
one image or multiple current-page images, write independent notes, delete or
revise an entry, save one private editable artifact containing both notes and
immutable image crops, reopen it without original files, and export a static
HTML report with the crops. IQA maps/official scores remain downstream-owned.

### Mandatory user story

1. Load image A (or A/B), draw ROI #1, type Title/Note, choose **Add ROI Memo**.
2. Draw ROI #2 elsewhere and add another note; repeat. The list shows ROI
   number, user title, coordinate/dimensions, image label and thumbnail.
3. Selecting a row shows its stored crop instantly. If original sources are
   still verified, one click also restores *that* ROI and physical viewport.
   If originals are missing, notes/crops remain fully readable with a simple
   "Original unavailable — saved crop shown" status.
4. **Update Note** modifies only text; **Replace ROI from Current Selection**
   explicitly creates a new crop/viewpoint and requires confirmation. Never
   silently mutate a historical crop on text update.
5. **Delete ROI Memo** removes only that one record and its private crop assets
   from the next saved revision; other entries and original files remain intact.
   Confirm or Undo; dirty-state indicator is mandatory.
6. **Save Memo** writes one versioned `.pxmemo` ZIP archive: review binding
   metadata and snapshots for every source in each ROI entry. Source file
   paths are private/local and never sent to HTML.
7. **Open Memo** fully validates a bounded archive before mutating the live
   library, then shows entries/crops even if all original images are gone.
8. **Export HTML** emits `index.html` + `images/*.png` for offline delivery.
   It contains ROI number, title, note, source display label, ROI coordinates,
   cropped pixel previews and capture time; **no** absolute local file paths,
   source hashes, native interpretation parameters or JavaScript.
9. Capture image bytes at **Add** time, from the same frozen reference-space
   ROI as W09b Finding; never re-crop the *current* image while saving a
   previously committed Memo. Native RAW/YUV numerics stay unchanged.

## Proposed compact panel

Header: `Memo (N) •` + Open / Save / Export HTML (the three document commands).
Upper: scrollable ROI memo list with small crop thumb and title/coordinate.
Editor: Title, Note; `Add ROI` / `Update Note` / `Replace ROI` / `Delete`.
Footer: current crop preview/status, collapsible `Locate original…` only if
source verification fails. Technical SHA/profile/CAS details never become
normal-use buttons.

Keyboard: Enter on list navigates; Ctrl+S saves; Delete on focused list opens
Delete confirmation; Ctrl+N creates a new ROI memo only with a valid selection.
Each control has a stable objectName, accessibleName, tooltip and enabled-state.
A visible dirty marker disambiguates saved vs unsaved work.

## IQA Dock coexistence

IQA Reference Lite contributes `referenceIqaWorkspaceDock` on the **right**,
and private Enterprise IQA will also own its own contributed Dock. Memo remains
`namedReviewDock` and cannot import reference/SUB internals.

- When both docks are visible and there is >= 650 logical px of usable right
  dock height, use **vertical split**: IQA top ~65%; Memo bottom ~35%, with a
  user-resizable native QMainWindow splitter. Retain right dock width.
- At compact 1400x880 / insufficient available height, use **tabs** inside the
  same right dock area instead of stacking two cramped controls. User switches
  IQA/Memo tabs; no resize-triggered moving while a user is dragging.
- Initial placement only, or explicit `Arrange Side Panels` action.
  Subsequent user resizing, floating, tabbing and dock state wins; no automatic
  re-layout on every Memo toggle and **never** activate W06 Review preset.
- If no IQA contributed Dock exists, Memo is the single right Dock. If the
  private IQA Dock is loaded later, generic host locates it from contributed
  QDockWidgets by contract/capability (not private import/name).
- `View → Memo` always toggles visibility independently; dock X stays in sync.
  W06 cleanup must not destroy generic Dock restore, offscreen recovery,
  lifecycle ownership or QSettings single-owner semantics.

## Data/persistence contract

Keep `.pxreview` V1 readable as **legacy metadata-only local notebook**;
do not silently change W09a JSON schema v1. New `.pxmemo` v1 ZIP contains:

```text
manifest.json                    # kind, schema, explicit entry->asset bindings
review.json                      # W09a ReviewDocumentV1 (private local metadata)
images/<finding-uuid>/<source-uuid>.png
```

Use SHA-256 of each included PNG, explicit half-open reference ROI and
source-key mapping. Each saved ROI must have a crop for each bound source,
or a **visible explicit failure**; no silently incomplete archive.
Crops are canonical 8-bit previews, clearly labeled as such, *not* native
measurement arrays. Text is UTF-8; ZIP member names are allowlisted and
unique; reject traversal, duplicate entries, excessive decompression,
large/unbounded files and unsupported versions. Write same-directory temp +
fsync + atomic publish with overwrite conflict protection and cancel cleanup.
A future migration from V1 may capture missing crops only after explicit source
revalidation; metadata-only historical entries remain readable.

Report exporter must render exclusively from **saved archive assets**.
It may not attempt source file reads or accidentally include private paths.
Escape HTML content, use relative URLs and no external dependencies; include
static CSP and no JavaScript.

## Branch and acceptance gates

PR #223 (W05/W06 retirement): clean redundant UI/runtime; no Memo changes.
PR #222: W09b Verified Finding/Restore foundation. It remains independent.
**This PR**: advanced Memo V2 data/GUI/HTML/IQA Dock coexistence; Draft until all
of the following run at exact HEAD:

1. 1 image / 3 distinct ROIs / Add→Update→Delete one→Save→Restart→Open;
   two remaining entries retain exact labels, ROI geometry and crops.
2. 2/4/6 image entries, valid Gray/RGB/RAW/YUV preview crops, exact bounds,
   reject stale ROI and mixed source generation during worker completion.
3. Remove original image files: Open preserves notes/thumbnails/offline report;
   viewer restore reports unavailable rather than inventing current state.
4. HTML open from copied directory with no PixelScope/source access; all assets
   available, no private path/hash leak or script injection.
5. Archive malformed/zip-bomb/duplicate path/SHA mismatch/truncated PNG,
   wrong source binding, path conflict and cancellation negative tests.
6. IQA-only, Memo-only, both at 1400x880 and 1920x1080; vertical split/tabs;
   hide/show/float/close/reopen; compact split and normal-GC teardown.
7. Windows CPython 3.10/PySide6 native focused/full pytest, independent
   exact-HEAD code review, screenshot evidence and manual DPI matrix.

**Not yet implemented in this contract commit:** storage, GUI, export and
layout changes. Do not interpret the contract as acceptance.

Co-authored-by: ChatGPT <noreply@openai.com>
