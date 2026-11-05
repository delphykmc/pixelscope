# Statistics

<!-- pixelscope:screenshot statistics-workspace -->

Statistics reports numeric measurements for sources on the Current Comparison Page.

## Analysis region

With no ROI, measurements describe the full image. With an ROI, the same shared rectangle is used for compatible sources. The Statistics workspace also provides exact **X, Y, Width, Height** entry for repeatable ROI placement.

## Values

The table reports channel-appropriate measurements such as sample count, minimum, maximum, mean, and standard deviation. The available channel rows depend on whether the source is Gray, RGB, Bayer/RAW, or native YUV.

Statistics is based on source analysis data, not on presentation-only display gain.

## Raw and Pivot

**Raw** preserves the original per-image/channel table and its CSV format. **Pivot** presents metrics as rows (Mean, Std, P99 by default), with one column per Current Comparison Page source (up to six). Select **All metrics** or **Percentiles** and filter the channel without triggering new analysis. Column headers use the source's current qualified Display Alias; reordering images changes column order, not source identity.

Select a **Pivot reference** independently of the primary image or Difference A/B pair. Choose **Values**, **Absolute Δ** (target − reference, native unit), or **Relative Δ (%)** (absolute Δ / |reference| × 100). Deltas are calculated from full-precision W02 measurement values, not the rounded screen text. Incompatible native format/effective bits, CFA phase, YUV chroma footprint, unequal sample counts, mismatched metric definition or ROI, and unavailable/nonfinite values disable Delta; hover to see the reason. Zero reference retains absolute Δ but makes relative Δ unavailable.

Native statistics use **native code values**, not normalized [0,1] presentation values. The metric unit is shown separately; a native sample count, complete numeric state, effective precision and captured ROI are available in the tooltip. W02 results that are pending, cancelled or stale cannot appear in Pivot as current measurements.

## Export

The existing Statistics action continues to export the **unchanged legacy Raw CSV** even when Pivot is visible. The separate **Export Pivot CSV…** action writes typed Pivot values with 17 significant digits, native unit, state, sample count, absolute Delta and relative Delta (%) in separate columns. Ctrl+C in Pivot also copies typed, high-precision values with channel and unit labels. Neither action requests recalculation, and Pivot export is unavailable without a valid current Statistics token.

## Related topics

See [Inspect an ROI](../workflows/inspect-roi.md) and [Histogram](histogram.md).
