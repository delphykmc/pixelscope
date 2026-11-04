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

## Reusing native YUV profiles

The YUV dialog uses the same Recent/Favorite library as RAW, with separate entries by
native input family. A favorite saves dimensions and one of the currently supported
8-bit YUV444/YUV422/YUV420 tightly packed Y+UV interpretations; it cannot enable P010,
NV12, BT.709, or other currently unsupported formats. The dialog displays the source
filename, profile provenance, native byte-layout summary, and expected versus actual bytes.

Native YUV requires an **exact** file-size match. Truncated inputs and trailing bytes
are shown separately and rejected. File-size matching does **not** verify that the actual
bytes use the selected interpretation. The YUV-to-Generic RAW option still uses the
existing RAW workflow; neither a filename extension nor a saved favorite silently
changes native source identity or reloads an already registered source.

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
