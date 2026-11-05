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

## Native layouts and Difference

Use the existing Single View and Multi View controls for source comparison. The
current comparison page contains at most six sources and is the sole analysis
working set. Use the Files workspace to choose sources and **Primary** for the
source reference; **Active** is the currently focused source.

Use the existing Difference panel's Reference/Target selectors and an explicit
**Calculate** request for new differences. Cached results remain generation
and channel bound. There is no additional Original 2/4, A/B/Diff, or Diff Focus
preset state or hidden toolbar selector. Physical zoom, Sync and reference ROI
retain their existing viewer/analysis ownership.

## Quick Compare

Press **T** for persistent source-only comparison: the last source on the Current Comparison Page becomes Primary, and the others shift one position. Repeat T to cycle through the sources in Single or Multi View. Difference is never included; choose its Primary control explicitly if desired. The former hold-B Blink presentation is removed.

Drop A and then B, or drop exactly two images into Files or Image View, to prepare a compatible Difference in the background while the sources remain visible. Difference starts hidden. When **Diff** becomes available, select it to show the cached result. Selecting sources in Files alone does not start this background calculation; dropping three or more files does not choose an arbitrary new pair.

## More than six images

Selection may exceed the six-slot presentation capacity. See [Compare more than six images](compare-many-images.md).

## Related analysis

Continue with [ROI](inspect-roi.md), [Histogram](inspect-histogram.md), [Line Profile](inspect-line-profile.md), or [Difference](use-difference.md).
