# Memo — notes for the current comparison ROI

Memo keeps a list of ROI records for the images you are currently inspecting.
It does not browse files or automatically find notes for a newly selected image.
Session remains the way to resume the overall inspection setup.

## Add and edit ROI notes

1. Open your images and choose **View > Memo** (**Ctrl+Shift+M**).
2. Draw a rectangular ROI with **Ctrl+drag**. A new ROI entry is captured and the
   note starts empty. Wait for the short image capture to finish, then type.
3. Title and Note edits immediately update that entry in memory. There is no
   Update button. Captured crop pixels remain unchanged when text is edited.
4. Draw a different ROI to start another blank note. Select an earlier entry in
   the ROI list to see its note and select its ROI. For already loaded images this
   centers the Viewer on that ROI, preserves zoom and does not reload them. Opening a saved Memo can restore
   its recorded original view after source verification.
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

**Save Memo…** creates a named folder. The suggested name includes the first source
name and local date/time. There are no separate Export commands:

```text
Memo_scene_date/
  Memo_scene_date.pxmemo   metadata and relative file map
  index.html              report
  src/
    crops/                exact undecorated 8-bit ROI PNGs
    statistics/           optional native CSVs
```

Open `index.html` directly or click **Open report** in the Memo save status. Open
the `.pxmemo` in PixelScope to edit notes. Move/copy the whole folder together;
moving only the map loses its referenced evidence. No extraction is needed.

PNG files contain only captured ROI pixels without text or margins. Source basename
and ROI x/y/width/height appear in HTML and metadata. New saves use only src/crops. Saving consumes the recorded evidence; it does not recrop current
images or recalculate Statistics. Unsaved edits are temporary and are discarded
when the image selection changes or the application closes.

Older ZIP `.pxmemo` and legacy `.pxreview` still open. Saving them creates the new
folder and preserves the original file. Old PixelScope versions may not read the
new map format, but the HTML and images can be opened directly. CSV values retain
their native numerical meaning. Full original images are not copied into the folder.

Saving again keeps the folder in place, backs up files and commits metadata last. Edited
or unrelated files/directories are protected. Failed saving keeps the earlier
generation, and an initial failed save leaves notes Unsaved. If rollback cannot
restore the previous folder, the error gives its retained recovery location. Keep
an untouched Memo folder; edit a copy of its report for your own reporting work.
If saving succeeded but temporary backup cleanup failed, the header remains Saved
and the status gives a cleanup warning/location. The new Memo is usable and Save
can be retried normally.

The editable notebook may contain private original paths in its internal record.
Its HTML uses relative assets and omits automatic original paths. Share only the
HTML and `src/` if original-path metadata should be excluded.
User-written titles, notes and image names are included in the report.

## Changing images and reopening

Changing selected images, their order or the comparison page clears the current
ROI list and editor and starts a new temporary notebook. Returning to previous
images does not retrieve notes automatically. The program does not scan files,
match image sets or maintain a cross-file Memo catalog.

**Open Memo…** explicitly loads saved ROI records. Selecting an ROI attempts to
verify and reopen its original images; this direction is Memo-to-viewer only.
If originals are missing, changed or need unavailable RAW/YUV input settings, the
note remains readable; no image fallback is shown in Memo. Crops remain available
in the HTML report. Memo has no file browser or Locate button.
To supply native input settings, open originals normally through File, then open
the Memo. Legacy `.pxreview` notes remain readable but have no stored historical
crop; migration never invents old pixels.

Memo has no crop preview or coordinate summary. A genuine write lock or denied
write permission can still prevent saving; close the application holding the file
or check permissions, then retry.
