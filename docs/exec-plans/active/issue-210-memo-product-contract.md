# PixelScope Memo — product contract and UX acceptance (2026-11-06)

## Separate user jobs

- **Session (.pixelscope)**: continue an entire editing/inspection workspace — registered files, selections, view arrangement, and application-specific state. It is not an inspection report.
- **Memo (.pxreview)**: save a *collection of inspection points*. Each point binds a human-readable title/note to one or more specific image sources, the exact ROI/line in reference coordinates, and enough display/camera state to navigate back to the same location. Source identity and optional historical numeric provenance are internal integrity constraints, not user commands.

## Essential path — must be executable without explaining internals

1. Open normal PNG/JPEG, Bayer RAW, or native YUV in PixelScope as usual.
2. Draw ROI, open **View → Memo**, type title and note, press **Add Memo**.
3. Click a different Memo entry: the *selected* images, exact ROI and physical view center/scale must be restored from that entry. Do not require users to click Verify Source or Activate Finding.
4. **Save Memo…** saves the editable local notebook (one .pxreview file). **Open Memo…** opens it and navigates to the first entry when sources are available.
5. Missing/replaced file: keep the note readable, show a concise problem and offer **Locate image…**. No silent substitution, automatic disk-wide discovery or false claim of a historical metric being current.
6. **Export ROI PNGs…** saves one file per image in the current comparison page using the exact reference ROI. It is not an ROI-screenshot button and does not require first saving a Memo.

## Distinguish local notebook from portable report

A local Memo may contain original absolute file paths for click-to-reopen, with explicit local-only privacy semantics; a portable report **must strip local paths**. This remains a separate user-selectable export, not a replacement for Session. The intended report is `index.html` plus `images/*.png` and a minimal portable manifest, readable without PixelScope; it must show captured ROI pixels even after original sources become unavailable. **This report format and offline image snapshots are NOT implemented or accepted in this PR slice yet.**

## UI budget

Always visible in Memo: short list, title, note, **Add Memo**, **Update**, **Delete**, **Export ROI PNGs**, **Open Memo**, **Save Memo**. Only reveal **Locate image…** for an unresolved source. Do not expose Source SHA-256, RAW/YUV native profile checks, W02 snapshot internals, manual Verify or manual Activate as ordinary UI. View → Memo is a reversible show/hide toggle; opening Memo must not alter the workspace.

Remove redundant Open/Workspace/Preset/A-B toolbar controls; preserve File/Open/DnD, View visibility, and existing Difference Image1/Image2 controls. No surprise 2/4/A-B-Diff reordering.

## Acceptance criteria

- On an already-loaded RGB image: add two Memos with different ROIs and viewport positions; clicking each entry moves the viewer to the saved image/ROI/viewport. Same for two source images.
- Restart app → Open .pxreview → click one memo: exact source paths are revalidated in the background and the current image/ROI state restored with no manual verification when unchanged; missing/changed files require explicit correction.
- Session restoration still restores the full workspace; Memo never copies the Session dock layout or supersedes the source selection authority.
- GUI screenshot at 1400×880 shows no toolbar Open/Workspace/Preset/Reference-A/Target-B clutter, and no SHA/Profile/Verify/Activate panels in the normal Memo view.
- No implicit Difference Calculate or fake current IQA/Statistics results.
- Native Windows full suite, real Qt end-to-end and independent exact-HEAD review before merge.
