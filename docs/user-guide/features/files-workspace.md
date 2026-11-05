# Files Workspace

<!-- pixelscope:screenshot files-workspace -->

The Files workspace is the source-registration and selection surface for PixelScope.

## What it shows

Registered files remain visible even when they are not on the Current Comparison Page. Folder-backed sources retain their folder identity so that matching Folder Positions can be compared later.

Selection is separate from registration. A source can be Registered without being Selected, and Selected can contain more sources than the six slots visible on one Comparison Page.

## Common actions

Use Files to select a comparison set, set a current-page source as **Primary**, show Selected sources in Multi View, remove registered entries, or use **Compare same position with...** for folder-backed sequences.

Removing an entry from Files removes it from PixelScope's current registration state; it does not delete the source file from disk.

## Workspace layout presets

Use **Workspace** in the main toolbar to switch between **Compare**, **Analyze**,
and **Review**. These presets change Files/Statistics space, Plots visibility,
and dock/splitter layout only. Compare prioritizes source identification and image
space; Analyze allocates more room for Statistics and opens Plots; Review provides
a comparison inspection layout without a Findings panel until that feature ships.

The adjacent **Original 2/4**, **A/B/Diff**, and **Diff Focus** controls select
*which sources are presented*, not the Workspace layout. Changing Workspace
does not alter Registered/Selected sources, the Current Comparison Page,
Reference A/Target B, Primary, Active, ROI, zoom intent, or Difference calculations.
Existing **View > Reset Workspace Layout** resets the saved workspace layouts;
manual splitter and floating Plots adjustments are retained per preset.

## Related topics

See [Core concepts](../getting-started/concepts.md), [Open folders](../workflows/open-folders.md), and [Compare folder positions](../workflows/compare-folder-positions.md).
