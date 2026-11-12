# Memo — notes for the current comparison ROI

Memo keeps a list of ROI records for the images you are currently inspecting.
It does not browse files or automatically find notes for a newly selected image.
Session remains the way to resume the overall inspection setup.

## Add and edit ROI notes

1. Open your images and choose **View > Memo** (**Ctrl+Shift+M**).
2. Opening Memo enables the **Record ROI** switch when selected originals are ready.
   Without ready selected images the switch is disabled. Draw a rectangular ROI with
   **Ctrl+drag**. A new ROI entry is captured and the
   note starts empty. Wait for the short image capture to finish, then type.
3. Title and Note edits immediately update that entry in memory. There is no
   Update button. Captured crop pixels remain unchanged when text is edited.
4. Draw a different ROI to start another blank note. Select an earlier entry in
   the ROI list to see its note and select its ROI. For already loaded images this
   fits the ROI with surrounding context without reloading the originals. Opening a saved Memo can restore
   its recorded original view after source verification.
5. Turn the **Record ROI** switch off to keep reading/editing notes while drawing ordinary
   analysis ROIs without adding records. Turning recording back on only captures
   future ROI gestures; it does not duplicate the currently selected ROI.
6. With the ROI list focused, press **Delete** to remove selected entries. The next
   remaining entry is selected; repeated Delete continues removing records.
   **Ctrl+A** selects all entries for deletion. The deleted analysis box is cleared.
   There are no Add/Delete buttons. Delete inside Title/Note edits text normally.
7. **Esc** clears the active analysis ROI and Memo list selection, cancels pending
   Memo capture/statistics/restore, and keeps existing notes. Normal analysis may
   still refresh after clearing its ROI; Memo does not restart canceled capture.

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

Successful Save opens `index.html` automatically in the default browser. Open
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
and a warning dialog gives the cleanup location. The new Memo is usable and Save
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

Hiding Memo disables recording, cancels pending capture, clears the active analysis
ROI and hides all Memo boxes. Note records remain in memory. Reopening enables
recording for future ROI gestures, without capturing ROIs drawn while it was hidden.

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

The footer contains only Open Memo and Save Memo, without routine status text or
report links. The header Saved/Unsaved marker remains. Write/open failures use a
warning dialog. Revisited ROIs reuse the existing native Statistics/Histogram cache;
changed source generations, interpretation or bin settings use their normal keys.
