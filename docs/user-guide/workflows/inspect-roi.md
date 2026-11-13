# Inspect an ROI

<!-- pixelscope:screenshot roi-exact -->

Use a Region of Interest (ROI) when analysis should describe a specific rectangular source region rather than the full image.

## Draw an ROI

Use **Ctrl+drag** in Image View to create the shared ROI rectangle. PixelScope expresses the ROI in the source/reference coordinate system used by the comparison.

## Enter an exact ROI

For repeatable measurements, open **Statistics > Region > Edit**, enter **X**, **Y**, **Width**, and **Height** in the ROI dialog, then apply the region. Exact entry is preferable when you must compare the same coordinates across data sets.

Region shows a compact bounds summary with full coordinates in its tooltip. In a narrow sidebar, the summary moves below Bounds/Edit to use the available width; widening restores the compact layout. This does not change the selected ROI or its numerical results.

## Clear the ROI

Use `Esc` or **Edit > Clear ROI** for the application action.

## What uses the ROI

Statistics and Histogram use the ROI when active. Difference numeric metrics can use the ROI while the Difference preview remains a full-frame visual map, so do not infer the metric domain only from the preview extent.

If a new comparison context cannot represent the existing ROI consistently, PixelScope clears it instead of silently clipping it to a different region.

Temporary Pick membership does not replace the Current Comparison Page as the normal analysis working set.

## Troubleshooting keywords

**Ctrl+drag**, **exact ROI**, **X Y width height**, **ROI cleared**, **full image**, **Esc**.
