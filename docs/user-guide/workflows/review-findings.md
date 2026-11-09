# Memo — keep comparison notes and ROI images

A **Session** saves your source selection and inspection setup to continue work.
A **Memo** keeps several inspection points with notes and saved ROI images.
You can read the saved evidence without the originals and reuse it in a report.

## Add and revisit a memo

1. Open a PNG/JPEG/BMP, RAW or YUV image through the existing File menu or drag-and-drop.
2. Draw a rectangle on the image. Select **View > Memo**.
3. Type a short Title and Note, then select **Add Memo**. Wait for capture to finish:
   each image on the current page contributes a frozen ROI PNG.
   In Single View, the memo records the visible original image; Multi View records
   the comparison page. Recording does not change your current selection.
4. Repeat for another ROI. Select either entry in the Memo list: the selected
   image(s), saved ROI and physical zoom/center are restored automatically.
5. **Update Note** edits text while preserving its original crop. **Delete** removes
   only that Memo entry and its crops. Adding another Memo creates another ROI record.

A Memo does not calculate Difference or replace current Statistics. To also keep
native numeric results, check **Include current ROI statistics** before adding.
The current ROI Statistics must already be displayed; if they are pending, wait
or uncheck the option. Saved CSVs identify the ROI, channels, native domain, sample
counts and capture time. Changing a note later never recomputes its saved values.
For a Single View note with Statistics, select only that image; use Multi View
to keep the comparison page and its per-image Statistics together.

## Local save and reopen

Use **Save Memo…** to save one editable `.pxmemo` notebook containing all entries,
ROI PNGs and any saved Statistics CSVs. It retains image references, ROI/line and
enough view state to revisit each point, without embedding full originals.
An unsaved indicator and close confirmation help avoid losing notes.

For local click-to-reopen, `.pxmemo` contains the absolute paths of the
original image files. **Treat the editable notebook as private/local** and do
not distribute it as an anonymized report. If the original files are removed
or modified, open the notebook to read the notes and saved crops. The panel says
the original is unavailable; **Locate image…** can reconnect it. No silent
relinking or substitution occurs. Legacy `.pxreview` files remain readable, but
have no stored crop: converting them cannot recreate an image from the past.

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

## Reuse evidence or share a simple HTML report

Select **Export Report…** and choose a parent folder. PixelScope
creates a new **PixelScope Memo** folder (with a number if one already exists).
Open `index.html` in a browser, or copy the PNGs and any Statistics CSVs into your
own report. Source numbers in CSV follow the image order for that memo.

Export uses stored crops and values, so it also works without originals. Share
the entire HTML folder to retain its relative images and CSV links. Automatic
original file paths are omitted; your titles, notes and image names are included.
The editable notebook remains the way to continue editing notes in PixelScope.
