# Files Workspace

<!-- pixelscope:screenshot files-workspace -->

The Files workspace is the source-registration and selection surface for PixelScope.

## What it shows

Registered files remain visible even when they are not on the Current Comparison Page. Folder-backed sources retain their folder identity so that matching Folder Positions can be compared later.

Selection is separate from registration. A source can be Registered without being Selected, and Selected can contain more sources than the six slots visible on one Comparison Page.

## Common actions

Use Files to select a comparison set, set a current-page source as **Primary**, show Selected sources in Multi View, remove registered entries, or use **Compare same position with...** for folder-backed sequences.

Removing an entry from Files removes it from PixelScope's current registration state; it does not delete the source file from disk.

## Arrange the workspace

Resize the Files, Statistics and Image panes directly with their splitters.
Plots can be docked, hidden or floated using the native View/Plots controls.
There are no Compare/Analyze/Review layout presets: those duplicated existing
dock and splitter operations. PixelScope remembers the existing application
layout without maintaining multiple preset-specific versions.

Use **View > Reset Workspace Layout** to restore the default arrangement.
Resetting layout never changes Registered/Selected/Current Page, Primary,
Active, ROI, zoom or native Difference calculations.

## Related topics

See [Core concepts](../getting-started/concepts.md), [Open folders](../workflows/open-folders.md), and [Compare folder positions](../workflows/compare-folder-positions.md).
