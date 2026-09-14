# Use Difference

Difference is an explicit numerical and visual comparison between two compatible sources.

## Choose the pair

1. Put both sources on the Current Comparison Page.
2. Set the intended reference source as **Primary**.
3. Activate the comparison source as **Active**.
4. Open **Difference**.

## Calculate

Choose a valid channel and Difference options, then press **Calculate**. The calculation is explicit. Reopening a cached Difference can restore an already calculated matching result, but PixelScope does not silently establish a new Difference identity just because Active or viewer presentation changes.

## Compatibility rules

A valid pair must satisfy the Difference domain rules. Examples include compatible dimensions and source families. Gray/Bayer uses Gray semantics; RGB exposes color channels; native YUV Difference is available only for matching YUV layout/subsampling and exposes Y/U/V channels. Mixed YUV subsampling and YUV-versus-non-YUV pairs are rejected.

For mixed bit depths in supported non-YUV families, Difference uses the product's normalized full-scale semantics rather than comparing unrelated integer ranges directly.

## ROI and preview

An active ROI can restrict Difference metrics. The preview remains a full-frame map, so use the ROI/status information to understand the metric domain.

## If Difference is unavailable

Check that Primary and Active are both valid, distinct comparands on the current page, dimensions and channel families are compatible, and YUV layouts match where applicable. See [Troubleshooting](../troubleshooting/index.md).

## Troubleshooting keywords

**Difference unavailable**, **Primary**, **Active**, **Gray**, **Bayer**, **YUV**, **subsampling**, **mixed bit depth**, **Calculate**.
