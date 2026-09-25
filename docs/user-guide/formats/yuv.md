# YUV Guide

<!-- pixelscope:screenshot yuv-profile-dialog -->

PixelScope has an explicit native YUV path in addition to the Generic RAW interpretation available for `.yuv` files.

## Current native YUV support

Native YUV currently supports:

- 8-bit YUV444
- 8-bit YUV422
- 8-bit YUV420
- tightly packed storage
- Y-first storage with the current fixed UV ordering
- BT.601 Full-range preview semantics

YUV422 requires an even width. YUV420 requires even width and even height. PixelScope validates the expected byte size for the chosen dimensions and layout.

## Open a `.yuv` file

1. Open or foreground the `.yuv` source.
2. When interpretation is unresolved, enter **Width** and **Height**.
3. Choose **YUV420**, **YUV422**, or **YUV444** for native YUV, or **Generic RAW profile...** when the bytes should be interpreted through the RAW workflow instead.
4. Confirm the expected file size shown by the dialog.

A `.yuv` suffix by itself does not force native YUV semantics. Explicit metadata/profile choice owns the interpretation.

## Analysis semantics

Native YUV retains Y/U/V channel identity for supported analysis. Difference requires the two sources to use matching native YUV layout/subsampling and then exposes Y, U, and V. Mixed YUV subsampling or YUV-versus-non-YUV Difference is unavailable.

## Common errors

- Wrong width/height causing file-size mismatch.
- Odd width for YUV422.
- Odd width or height for YUV420.
- Selecting native YUV for a file that actually uses a different packing/order/bit depth.
- Expecting a Generic RAW `.yuv` profile to behave as native YUV.

## Troubleshooting keywords

**YUV420**, **YUV422**, **YUV444**, **BT.601 Full**, **UV order**, **size mismatch**, **Generic RAW**, **Difference unavailable**.
