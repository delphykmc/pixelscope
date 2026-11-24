# Difference

Difference compares two explicitly assigned, compatible sources and provides both a visual map and numerical metrics.

<!-- pixelscope:screenshot difference-analysis -->

## Roles

**Primary** is the viewer reference role and **Active** is the focused source. Confirm the actual pair in the Difference panel's **Image 1** and **Image 2** selectors before Calculate; the selected pair is the calculation authority.

## Explicit calculation and cache

Press **Calculate** to establish the current Difference result. PixelScope may reuse a cached result when its complete identity still matches, but cached presentation is not permission to silently calculate a different pair.

## Domains

Gray exposes Gray; Bayer exposes Mosaic, R, Gr, Gb and B. RGB/RGBA comparisons expose All, R, G and B and exclude alpha from color Difference semantics. Native YUV Difference is limited to matching native YUV layout/subsampling and exposes Y, U, and V. Unsupported family/size/CFA/subsampling combinations remain unavailable.

## Metric units

The Difference metric table distinguishes **Value** and **Unit** without changing the underlying numeric result or the explicit Calculate/cache contract. MAE, RMSE, P95/P99, and maximum absolute difference use **native code** for equal native bit depth, or **normalized [0,1]** for compatible mixed-depth comparisons. MSE uses the corresponding squared unit, PSNR uses **dB**, and Non-zero ratio is a dimensionless **ratio [0,1]** (not a percentage). Hover over a value for 17-digit numeric precision and nonfinite-state information.

## Display versus analysis

Image View Display Gain is presentation-only and separate from the Difference panel's Gain. Difference supports Absolute and Mask display modes, a threshold and its own Gain control. Choose Full image or Active ROI for numeric metrics; the Difference map remains a full-frame preview.

See [Use Difference](../workflows/use-difference.md) for the procedure and compatibility checks.
