# Issue #210: product feature audit and removal decisions (2026-11-06)

This audit replaces the assumption that passing a code test proves user-visible
improvement. It does not change W00 internal schema contracts.

## Non-overlapping jobs

**Session**: Save/open the **entire** working environment, including registered,
selected and picked sources, docks, layout, analysis controls and view state.

**Memo**: Record a **specific inspection point**, with selected source(s),
reference-space ROI/line, physical zoom and center, a title and explanatory note.
Clicking a Memo must revisit the image/ROI without a separate Verify/Activate
button. If source files are changed, keep note metadata readable and allow an
explicit Locate Image action. Internal verification is a consistency guard, not
an everyday feature to teach.

**Portable report**: Share a static HTML document and individual ROI PNG assets
that remain readable with no PixelScope installation and without private local
source paths. This is distinct from Session and from editable local Memo. W10
owns the portable export; do not add its incomplete UI yet.

## #210 inventory

| Work | Retain as needed | Remove or simplify in UI | User-facing acceptance |
|---|---|---|---|
| W01 Physical Pixel Zoom | Actual accurate 100/200/400% measurement | No extra scope | User invokes 100% and displayed/reference physical pixels agree |
| W02 Immutable Analysis | Typed numerical provenance and stale-result guards | Never expose token state as a primary user control | Existing Statistics/Difference results truthful |
| W03 Source Identity/Alias | Durable identity, meaningful headers | Duplicate alias/role selectors | Same-name images still distinguishable |
| W04 View State | Correct center, scale, sync for Memo/Session | Do not add separate view-state button | Clicking a Memo revisits exact ROI and zoom |
| W05 Comparison Presets | Internal comparison plan only where required | Remove exposed Preset/Original 2/4/A-B-Diff and duplicate A/B toolbar combos | Files/Picked/current page and existing Difference panel sufficient |
| W06 Workspace Presets | Dock persistence, recovery, reset and responsive layout | Remove Workspace selector and extra Open toolbar action | View menu, dock actions and saved layout remain canonical |
| W07 Statistics Pivot | User-facing Metric × Source comparison | Avoid new duplicate controls | Real visible rows with correct units and exact clipboard semantics |
| W08a/b RAW/YUV Profiles | Useful native image input parsing and profile reuse | Never require RAW/YUV validation for PNG/JPEG notes | Ordinary images create Memos with no profile dialog |
| W09a Review Record | Private editable .pxreview file for multiple inspection points | Avoid treating all Session properties as user-facing Memo fields | File roundtrip preserves note, ROI and source references |
| W09b Finding UI | Reframe as Memo; one-click list navigation; source checks internal | Delete manual Verify, Activate, everyday Source/Profile panel and technical statuses | PNG single source and multi-source ROI click→save→reopen→click works |
| W10 Offline Report | HTML + ROI PNGs + minimal manifest for recipients | Do not duplicate Session save or leak local paths | No PixelScope required to read the report |
| W13 Acceptance | Actual Windows UI, native GC, multi-DPI, IQA dock coexistence | No bypass by passing unit tests alone | Real pre/post comparison with keyboard/mouse interaction |

## Binding and privacy policy

- The editable, **local-only** Memo notebook may preserve original image paths
  specifically to support click-to-reopen. They are private metadata and must
  be identified as such before sharing.
- A static exported report includes only notes, ROI image crops, safe labels and
  useful dimensions; private local paths and internal W02/W09 hashes are omitted.
- SHA-256 or RAW/YUV interpretation is an invisible integrity check. It is
  **not** an independently selected feature, and must not block adding a normal
  PNG/JPEG memo when the actual loaded image is available.
- No silent candidate substitution on mismatch. Do not turn past IQA measurements
  into current results.

## Design acceptance checklist

1. Observe and document the **current workflow** first. Explain why the proposed
   UI reduces clicks/errors without repeating File/View/Picked/Difference.
2. Default view at 1400x880 has no Open, Workspace, Preset or tiny A/B toolbar
   widgets; Memo is a compact optional View dock.
3. Can a new user add one ordinary RGB note and retrieve its ROI without
   knowing "Native Profile", "Source Verification" or "Analysis Token"?
4. Does selecting an item move the actual image/ROI, not merely repopulate a text
   form? Does reopening the local Memo work after restart?
5. Missing image path: show old text and only then an explicit Locate Image.
6. Does one-click Memo navigation preserve reference pixel coordinates without
   touching unrelated workspace docks or invoking Difference Calculate?
7. Full Windows native normal-GC and exact-head independent review are required
   before calling this work complete.

**Not yet accepted**: complete portable HTML/PNG report and offline ROI snapshots
that survive permanent loss of original files. Tracking the design is not
equivalent to implementing it. W09b stays Draft until the essential Memo path
has real Qt evidence.
