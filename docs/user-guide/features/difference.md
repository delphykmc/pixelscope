# Difference

Difference compares two explicitly assigned, compatible sources and provides both a visual map and numerical metrics.

<!-- pixelscope:screenshot difference-analysis -->

## Roles

**Primary** is the reference role and **Active** is the focused comparison role. Both must identify a valid current-page pair before a new calculation can be established.

## Explicit calculation and cache

Press **Calculate** to establish the current Difference result. PixelScope may reuse a cached result when its complete identity still matches, but cached presentation is not permission to silently calculate a different pair.

## Domains

Gray/Bayer comparisons use Gray semantics. RGB/RGBA comparisons exclude alpha from color Difference semantics and expose color channels. Native YUV Difference is limited to matching native YUV layout/subsampling and exposes Y, U, and V. Unsupported family/size/CFA/subsampling combinations remain unavailable.

## Metric units

The Difference metric table distinguishes **Value** and **Unit** without changing the underlying numeric result or the explicit Calculate/cache contract. MAE, RMSE, P95/P99, and maximum absolute difference use **native code** for equal native bit depth, or **normalized [0,1]** for compatible mixed-depth comparisons. MSE uses the corresponding squared unit, PSNR uses **dB**, and Non-zero ratio is a dimensionless **ratio [0,1]** (not a percentage). Hover over a value for 17-digit numeric precision and nonfinite-state information.

## Display versus analysis

Display gain is presentation-only. An ROI can restrict Difference metrics while the Difference map remains a full-frame preview.

See [Use Difference](../workflows/use-difference.md) for the procedure and compatibility checks.
