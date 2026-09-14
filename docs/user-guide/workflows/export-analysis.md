# Export Analysis Results

PixelScope exports the current analysis state; export does not silently recalculate a different analysis just to create a file.

## Statistics CSV

Use **File > Export Statistics CSV...** to save the current Statistics table for the active full-image/ROI analysis context.

## Histogram CSV

Use **Export Histogram CSV...** to save the exact currently plotted Histogram series, including analysis scope/bounds, source/series/channel identity, bin information, counts, and current plot modes.

## Line Profile CSV

Use **Export Line Profile CSV...** to save the exact currently plotted samples with the selected line coordinates, source/series/channel identity, sample position, and displayed value.

## Difference image

Use **Export Difference Image...** to save the current Difference presentation as PNG. Export is available only after an explicit **Calculate** has established an active current Difference result. The exported image follows the settled Difference presentation, including applicable Absolute/Mask, threshold, Difference Gain, and channel presentation; toolbar/window chrome is not part of the PNG.

A cached Difference entry by itself does not establish a new exportable current result, and export does not call Calculate for you.

## Export folder and failures

Export dialogs use the configured Default Export Folder and last-used-folder fallback. Cancelling does not change the workspace. A write failure reports an error and leaves the current analysis intact.

## Troubleshooting keywords

**Export Statistics CSV**, **Export Histogram CSV**, **Export Line Profile CSV**, **Export Difference Image**, **Difference export unavailable**, **Default Export Folder**.
