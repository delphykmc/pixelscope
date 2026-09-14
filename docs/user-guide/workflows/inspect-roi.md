# Inspect an ROI

Use a Region of Interest (ROI) when analysis should describe a specific rectangular source region rather than the full image.

## Draw an ROI

Use **Ctrl+drag** in Image View to create the shared ROI rectangle. PixelScope expresses the ROI in the source/reference coordinate system used by the comparison.

## Enter an exact ROI

For repeatable measurements, open **Statistics** and enter **X**, **Y**, **Width**, and **Height**, then apply the region. Exact entry is preferable when you must compare the same coordinates across data sets.

## Clear the ROI

Use `Esc` in the ROI interaction context or **Edit > Clear ROI** / `Ctrl+Shift+R` for the application action.

## What uses the ROI

Statistics and Histogram use the ROI when active. Difference numeric metrics can use the ROI while the Difference preview remains a full-frame visual map, so do not infer the metric domain only from the preview extent.

If a new comparison context cannot represent the existing ROI consistently, PixelScope clears it instead of silently clipping it to a different region.

Temporary Pick membership does not replace the Current Comparison Page as the normal analysis working set.

## Troubleshooting keywords

**Ctrl+drag**, **exact ROI**, **X Y width height**, **ROI cleared**, **full image**, **Ctrl+Shift+R**, **Esc**.
