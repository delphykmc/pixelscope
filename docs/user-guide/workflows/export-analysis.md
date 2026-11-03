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

## Analysis Bundle (versioned ZIP)

Use **File > Export Analysis Bundle...** after Statistics has finished displaying.
The bundle captures independently frozen **Statistics, Histogram, Line Profile,
and Difference** results when each is fully presented and current. Each feature
has its own request/generation token: an unavailable, pending or stale feature
is excluded rather than importing its old values. At least one current feature
is required to export. It does not trigger another analysis.

The context stores exact **reference-space ROI coordinates** (or Full Image),
source generations, native channel sample counts, non-path profile signatures,
request identity, and numeric definition revisions. Histogram series freeze
native bin edges and integer counts, and Line Profile series freeze native sample
coordinates/values separately from presentation modes. Difference metrics freeze
the exact ordered pair, channel, domain, ROI and Difference Cache identity.

A ZIP contains `manifest.json`, `data/context.json`,
`data/measurements.json`, and `data/measurements.csv`. This **portable-default**
export does not include source names, original source bytes, filesystem paths,
arbitrary profile data, or annotations. Source content verification is explicitly
`unverified` unless a matching SHA-256 verification has been established; file
size or modification time alone is not proof of unchanged content. The manifest
records SHA-256 for each ZIP entry.

When analysis is pending, replaced, stale, or has changed ROI/source generation,
the export is unavailable. The destination extension is resolved before any
overwrite confirmation. The ZIP is written to a temporary sibling and published
atomically; cancellation or an I/O error does not publish an incomplete bundle.

This bundle is **not** a full HTML/PNG Review Report. Named findings and report
composition belong to the separate Review workflow. Existing individual CSV/PNG
commands remain available, with their original file layouts and numerical rules.

## Export folder and failures

Export dialogs use the configured Default Export Folder and last-used-folder fallback. Cancelling does not change the workspace. A write failure reports an error and leaves the current analysis intact.

## Troubleshooting keywords

**Export Statistics CSV**, **Export Histogram CSV**, **Export Line Profile CSV**, **Export Difference Image**, **Difference export unavailable**, **Default Export Folder**.
