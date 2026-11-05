# Memo — save inspection points

A **Session** saves the whole PixelScope workspace for continuing work. A
**Memo** saves individual image inspection points so you can return to a
particular image/ROI and see the note attached to it.

## Add and revisit a memo

1. Open a PNG/JPEG/BMP, RAW or YUV image through the existing File menu or drag-and-drop.
2. Draw a rectangle on the image. Select **View > Memo**.
3. Type a short Title and Note, then select **Add Memo**.
4. Repeat for another ROI. Select either entry in the Memo list: the selected
   image(s), saved ROI and physical zoom/center are restored automatically.
5. **Update** edits note text. **Delete** removes only that Memo entry.

A Memo does not calculate Difference or replace current Statistics. If an ROI
or source is missing, the note stays readable and a concise status explains
what needs correcting. **Locate image…** appears only when the original image
cannot be automatically reopened; it is not part of normal note-taking.

## Local save and reopen

Use **Save Memo…** to save an editable `.pxreview` notebook with multiple memo
entries. This is not a Session. It stores text, image references, ROI/line and
just enough view state to revisit each saved point. It does **not** embed full
original image arrays or screenshots.

For local click-to-reopen, `.pxreview` contains the absolute paths of the
original image files. **Treat the editable notebook as private/local** and do
not distribute it as an anonymized report. If the original files are removed
or modified, open the notebook to read the notes and use Locate image when
appropriate. No silent relinking or substitution occurs.

**Open Memo…** loads a notebook and selects its first entry; clicking another
entry revisits that inspection point without a separate Verify or Activate
button. RAW/YUV originals may need a valid user-approved native input profile
when loaded in a fresh process; PNG/BMP/JPEG do not require RAW/YUV profile
dialogs. Internal source fingerprint checks run without a manual verification
panel.

## Save cropped ROI PNGs

With images selected and a rectangular ROI drawn, select **Export ROI PNGs…**
in the Memo panel and choose a directory. No Memo record needs to exist.

Each image on the current comparison page produces one PNG with the same
reference-pixel ROI, retaining its original reference dimensions. Output is a
canonical **8-bit display preview**, not raw Bayer values, native YUV planes or
a screenshot with selection overlays. Existing files are never overwritten.
An invalid/out-of-bounds ROI fails the operation without clamping.

## Portable HTML report — separate from editable Memo

A portable report is a different use case: an `index.html` plus ROI PNG
assets and a minimal manifest for recipients without PixelScope. It must not
include private source file paths. **Export of this self-contained HTML package
and permanent offline ROI snapshots is not implemented in this W09b slice.**
The distinction is deliberate; the presence of a design document or JSON
metadata alone does not make a report shareable.
