# Compare Images

This workflow covers ordinary visual comparison of two to six sources on the current page.

## Build the comparison

1. Register files or folders.
2. Select the desired sources in Files.
3. Show the Selected set in Image View.
4. Use **Multi View** (`Ctrl+2`) for side-by-side comparison or **Single View** (`Ctrl+1`) for focused inspection.
5. Use `1` through `6` to activate a visible slot.

## Choose a reference

Set a source as **Primary** when you need a stable reference role. **Active** follows the source currently in focus. Difference uses these roles but ordinary visual comparison does not require a Difference calculation.

## Explicit Comparison Presets

The **Preset** control in Image View offers five choices:

- **Workspace** — the existing automatic Single/Multi layout and complete Current Comparison Page.
- **Original 2** — show Reference **A** and Target **B** as two originals.
- **Original 4** — show the first four sources (A/B/C/D) on the Current Comparison Page. Reference A remains fixed while you choose another Target B/C/D.
- **A/B/Diff** — show the two selected original sources plus an existing valid Difference map.
- **Diff Focus** — concentrate on the currently valid cached Difference map.

The **A** and **B** selectors identify the exact runtime sources, even when filenames match. These are comparison-pair roles; they do **not** silently set the separate Primary, Active or Picked roles. To change Reference A, explicitly use the A selector. Changing B does not change Files Selected, source registration, Current Comparison Page or residency.

**A/B/Diff** reports *Not Calculated*, *Pending* or *Stale* instead of showing an unrelated Difference. **Diff Focus** does not display an old map when the requested pair has no valid cached result. Use **Difference > Calculate** explicitly to compute it; a Preset change alone never requests calculation. The separate two-file Drop-to-Prepare behavior remains available.

**Workspace** returns to the ordinary presentation. Temporary presets are not saved as Session v1 or durable Review documents. Physical zoom and center are preserved across settled source views, including hidden sources with **Sync Off**. Turning Sync on uses a common source anchor for the presented tiles. A page/source change cancels the temporary preset; zoom/navigation cancels a pending restore so a delayed callback cannot undo your action.

Preset tiles retain the page-local source numbers. The A/B labels remain fixed while **T** changes the separate source Primary. In multi-tile presets, arrows activate the presented originals. Explicit layout choices return to Workspace; number keys in Single/Diff Focus return to an original source. Statistics and other analysis still cover the full Current Comparison Page, including temporarily hidden sources.

## Quick Compare

Press **T** for persistent source-only comparison: the last source on the Current Comparison Page becomes Primary, and the others shift one position. Repeat T to cycle through the sources in Single or Multi View. Difference is never included; choose its Primary control explicitly if desired. The former hold-B Blink presentation is removed.

Drop A and then B, or drop exactly two images into Files or Image View, to prepare a compatible Difference in the background while the sources remain visible. Difference starts hidden. When **Diff** becomes available, select it to show the cached result. Selecting sources in Files alone does not start this background calculation; dropping three or more files does not choose an arbitrary new pair.

## More than six images

Selection may exceed the six-slot presentation capacity. See [Compare more than six images](compare-many-images.md).

## Related analysis

Continue with [ROI](inspect-roi.md), [Histogram](inspect-histogram.md), [Line Profile](inspect-line-profile.md), or [Difference](use-difference.md).
