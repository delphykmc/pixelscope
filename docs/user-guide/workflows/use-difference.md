# Use Difference

Difference is an explicit numerical and visual comparison between two compatible sources.

## Choose the pair

1. Put both sources on the Current Comparison Page.
2. Set the intended Primary and Active source context if useful.
3. Open **Difference** and confirm **Image 1** and **Image 2** (A/B) in its source selectors; the panel can select a pair independently.
4. Select the intended channel and metric scope.

## Calculate

Choose a valid channel and Difference options, then press **Calculate**. The calculation is explicit. Reopening a cached Difference can restore an already calculated matching result, but PixelScope does not silently establish a new Difference identity just because Active or viewer presentation changes.

Eligible two-source Quick Compare drops can prepare the numerical result in the background with Difference hidden. Select **Diff** when it becomes available to show that cached result. **Calculate** also reuses a matching cached map and metrics; its first display may still need to prepare the preview. Repeated hide/show does not require another numerical calculation while the matching result remains cached.

## Display Difference on a six-image page

When the Current Comparison Page contains six original images, **Calculate** or showing a cached result with **Diff** switches Image View to Single View to display Difference alone. The original images remain Selected; no sources are removed. Auto and Multi View are unavailable while this Difference is visible.

Turn **Diff** off in the toolbar to return to the previous comparison page, layout and view state. To change the layout, hide Difference first. See [Compare More Than Six Images](compare-many-images.md).

<!-- pixelscope:screenshot six-image-difference -->

## Compatibility rules

A valid pair must satisfy the Difference domain rules. Examples include compatible dimensions and source families. Gray uses Gray; Bayer exposes Mosaic, R, Gr, Gb and B; RGB exposes All, R, G and B; native YUV Difference is available only for matching YUV layout/subsampling and exposes Y/U/V channels. Mixed YUV subsampling and YUV-versus-non-YUV pairs are rejected.

For mixed bit depths in supported non-YUV families, Difference uses the product's normalized full-scale semantics rather than comparing unrelated integer ranges directly.

## ROI and preview

An active ROI can restrict Difference metrics. The preview remains a full-frame map, so use the ROI/status information to understand the metric domain.

## If Difference is unavailable

Check that both Difference selectors identify distinct compatible sources on the current page, dimensions and channel families are compatible, and YUV layouts match where applicable. See [Troubleshooting](../troubleshooting/index.md).

## Troubleshooting keywords

**Difference unavailable**, **Primary**, **Active**, **Gray**, **Bayer**, **YUV**, **subsampling**, **mixed bit depth**, **Calculate**.
