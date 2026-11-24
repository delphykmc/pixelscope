# Line Profile

Line Profile plots source values along a shared horizontal or vertical line.

<!-- pixelscope:screenshot line-profile-docked -->

## Define the line

Open the Line Profile tab and **Shift+drag** in Image View. PixelScope records the line in the shared source/reference coordinate system and reports its endpoints.

## Clear the line

Use **Edit > Clear Line Profile**. `Shift+Esc` is available while the Line Profile tab is current.

## Plot controls

Use Overlay, Separate by image or Separate by channel. The Y axis supports Native value, Normalized 0–1 and Difference from reference; choose the reference when that mode is active. The X axis supports Distance px or Normalized distance. These plot choices do not alter the original source samples.

## Scope

The plot follows the Current Comparison Page. If the current comparison can no longer represent the line consistently, the line may be cleared rather than silently changed.

See [Line Profile workflow](../workflows/inspect-line-profile.md).
