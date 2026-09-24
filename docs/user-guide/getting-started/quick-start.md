# Quick Start

Use this workflow to reach PixelScope's main comparison and analysis tools in about five minutes.

## 1. Start PixelScope

Open PixelScope. The **Files** workspace is the source list; **Image View** is the visual comparison area; Statistics, Plots, Difference, and IQA are analysis workspaces.

## 2. Register images

Choose **File > Open Images...** (`Ctrl+O`) for specific files, or **File > Open Folder...** (`Ctrl+Shift+O`) to register supported images discovered under a folder.

Opening a folder registers sources. It does not mean every registered image must be displayed or decoded immediately.

## 3. Select the images to compare

Select the images you want in the Files workspace and use the compare/show-selected action. Selected images form an ordered working set.

A Comparison Page can show at most six images. If more than six are Selected, use the page controls to move through them; the selection itself is not truncated.

## 4. Choose Single or Multi View

Use **Single View** (`Ctrl+1`) to focus on one selected source or **Multi View** (`Ctrl+2`) to see the current Comparison Page together. In a visible page, number keys `1` through `6` activate the corresponding page-local slot.

Zoom and pan in Image View to inspect detail. Pixel/cursor readout follows the native source coordinate system where the format supports it.

<!-- pixelscope:screenshot six-image-multiview -->

## 5. Mark an ROI

Use **Ctrl+drag** to draw an ROI, or enter exact **X, Y, Width, Height** values in Statistics. The ROI is shared by analysis views. If a new comparison context cannot represent the ROI consistently, PixelScope clears it rather than silently changing its bounds.

## 6. Read Statistics

Open **Statistics** to compare numeric values for the Current Comparison Page. Statistics uses the full image when no ROI is set and the shared ROI when one is active.

## 7. Compare a Histogram

Open **Plots > Histogram**. The plot represents the Current Comparison Page and identifies whether it is using the full image or ROI context.

## 8. Create a Line Profile

Open **Plots > Line Profile**, then **Shift+drag** in Image View to create a horizontal or vertical shared line. Use **Shift+Esc** while the Line Profile tab is current to clear it.

## 9. Calculate Difference

Choose the two images by setting **Primary** and **Active**, open **Difference**, choose the valid channel/options, and press **Calculate**. Difference is explicit: changing a viewer state does not silently recalculate a new pair.

## Next steps

Read [Core concepts](concepts.md), [Difference workflow](../workflows/use-difference.md), or the [Keyboard shortcut reference](../reference/keyboard-shortcuts.md).
