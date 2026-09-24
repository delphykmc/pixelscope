# Difference

Difference compares two explicitly assigned, compatible sources and provides both a visual map and numerical metrics.

<!-- pixelscope:screenshot difference-analysis -->

## Roles

**Primary** is the reference role and **Active** is the focused comparison role. Both must identify a valid current-page pair before a new calculation can be established.

## Explicit calculation and cache

Press **Calculate** to establish the current Difference result. PixelScope may reuse a cached result when its complete identity still matches, but cached presentation is not permission to silently calculate a different pair.

## Domains

Gray/Bayer comparisons use Gray semantics. RGB/RGBA comparisons exclude alpha from color Difference semantics and expose color channels. Native YUV Difference is limited to matching native YUV layout/subsampling and exposes Y, U, and V. Unsupported family/size/CFA/subsampling combinations remain unavailable.

## Display versus analysis

Display gain is presentation-only. An ROI can restrict Difference metrics while the Difference map remains a full-frame preview.

See [Use Difference](../workflows/use-difference.md) for the procedure and compatibility checks.
