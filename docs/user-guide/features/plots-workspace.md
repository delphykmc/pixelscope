# Plots Workspace

<!-- pixelscope:screenshot plots-floating -->

Plots contains Histogram and Line Profile in one movable workspace.

## Docking and floating

The workspace can be docked or floated using the normal PixelScope workspace controls. Its visibility, selected tab, and supported geometry state participate in workspace/session restoration.

## Histogram

Histogram compares value distributions for the Current Comparison Page and follows the current full-image/ROI analysis context.

## Line Profile

Line Profile compares values along the current shared line. Define a line with **Shift+drag** in Image View.

## Working with Compare, Analyze and Review

**Analyze** gives Statistics more vertical space and opens the existing
Histogram/Line Profile Plots dock. Tables retain native scrolling rather than
hiding rows. **Compare** allocates more room to the viewer; **Review** keeps a
review-oriented arrangement without displaying a placeholder Findings panel.
Moving a splitter or floating, closing, and reopening Plots affects layout only.
Changes are remembered separately for each Workspace preset, while the
application's existing QSettings dock and tab behavior remains in place.
For an off-screen floating window after monitor removal, PixelScope recovers
the window onto an available display. No workspace preset starts a calculation.

## Resetting the workspace

Use the application's workspace reset command when a floating/docked layout becomes inconvenient. Resetting layout does not change the source images.

See [Histogram](histogram.md) and [Line Profile](line-profile.md).
