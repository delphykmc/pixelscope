# Plots Workspace

<!-- pixelscope:screenshot plots-floating -->

Plots contains Histogram and Line Profile in one movable workspace.

## Docking and floating

The workspace can be docked or floated using the normal PixelScope workspace controls. Its visibility, selected tab, and supported geometry state participate in workspace/session restoration.

## Histogram

Histogram compares value distributions for the Current Comparison Page and follows the current full-image/ROI analysis context.

## Line Profile

Line Profile compares values along the current shared line. Define a line with **Shift+drag** in Image View.

## Resize and restore

Resize the image and Statistics panels directly, and dock, float or close
Plots as needed. The existing dock/splitter/QSettings layout is canonical;
there are no separate Compare/Analyze/Review layout snapshots. After a monitor
is removed, an off-screen floating window is recovered onto an available
display when its native title region cannot be reached.

## Resetting the workspace

Use the application's workspace reset command when a floating/docked layout becomes inconvenient. Resetting layout does not change the source images.

See [Histogram](histogram.md) and [Line Profile](line-profile.md).
