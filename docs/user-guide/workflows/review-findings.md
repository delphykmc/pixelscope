# Memo — notes for the current comparison ROI

Memo keeps a list of ROI records for the images you are currently inspecting.
It does not browse files or automatically find notes for a newly selected image.
Session remains the way to resume the overall inspection setup.

## Add and edit ROI notes

1. Open your images and choose **View > Memo**.
2. Draw a rectangular ROI with **Ctrl+drag**. A new ROI entry is captured and the
   note starts empty. Wait for the short image capture to finish, then type.
3. Title and Note edits immediately update that entry in memory. There is no
   Update button. Captured crop pixels remain unchanged when text is edited.
4. Draw a different ROI to start another blank note. Select an earlier entry in
   the ROI list to see its note and return to its saved ROI and zoom.
5. **Add ROI** adds a blank entry for the current ROI. **Delete** removes the
   selected ROI entry. These controls operate on ROI records, not image files.

Every ROI in the current Memo list is drawn in its matching original viewers with
a numbered label at the top-left. The selected record is highlighted. These
outlines are visual bookmarks; mouse controls and the single active analysis ROI
continue to work as before.

Single View records the visible original; Multi View records the comparison page.
An optional **Include current ROI statistics** checkbox captures already-presented
native ROI Statistics when an entry is added. Pending/stale results are never used.
For Statistics in Single View, select only that image; use Multi View for a page.

## One Save Memo command

The header uses an amber **Unsaved** marker for changes held in memory and a green
**Saved** marker after a successful save. Empty working state is **Ready**.

**Save Memo…** writes all ROI notes, frozen PNG crops, optional Statistics CSVs and
an offline `index.html` into one editable `.pxmemo` file. There are no separate
Export commands. A default filename includes the first source name and local
date/time. Beside the notebook, Save also creates a folder with the same name
ending in `_report`. Open its `index.html`, or click **Open report** in the Memo
save status. The folder contains ready-to-use `images/` PNGs and any `statistics/`
CSVs, so no extraction is needed for reporting.

Report PNGs show the base filename and ROI x/y/width/height in a footer below the
crop. HTML captions and PNG filenames also identify the crop. The archived PNGs
remain undecorated. Saving consumes the recorded evidence; it does not recrop current
images or recalculate Statistics. Unsaved edits are temporary and are discarded
when the image selection changes or the application closes.

A `.pxmemo` is also a ZIP container. Open it in PixelScope to edit notes, or extract
a copy with an archive tool if you need its exact, undecorated 8-bit preview crops.
CSV values retain their native numerical meaning. Full original images are not
embedded.

Saving again refreshes an unmodified generated report folder. Edited report files
and unrelated folders are protected. If report generation fails, the status tells
you whether the `.pxmemo` itself saved successfully. Move or rename an edited
report folder before saving again to regenerate it. Keep the whole report folder
together when sharing its HTML and images.

The editable notebook may contain private original paths in its internal record.
Its HTML uses relative assets and omits automatic original paths. Share only the
HTML, images and Statistics folders if original-path metadata should be excluded.
User-written titles, notes and image names are included in the report.

## Changing images and reopening

Changing selected images, their order or the comparison page clears the current
ROI list and editor and starts a new temporary notebook. Returning to previous
images does not retrieve notes automatically. The program does not scan files,
match image sets or maintain a cross-file Memo catalog.

**Open Memo…** explicitly loads saved ROI records. Selecting an ROI attempts to
verify and reopen its original images; this direction is Memo-to-viewer only.
If originals are missing, changed or need unavailable RAW/YUV input settings, the
saved crop and note remain readable. Memo has no file browser or Locate button.
To supply native input settings, open originals normally through File, then open
the Memo. Legacy `.pxreview` notes remain readable but have no stored historical
crop; migration never invents old pixels.
