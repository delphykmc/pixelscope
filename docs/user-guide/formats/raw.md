# RAW Guide

PixelScope can open headerless RAW-like data when enough metadata is available to interpret its bytes. The filename suffix alone is not sufficient to infer every storage property.

<!-- pixelscope:screenshot raw-profile-dialog -->

## RAW-like files

`.raw` and `.data` use the RAW profile workflow. A `.yuv` file can also use **Generic RAW profile...** when it is intentionally being interpreted as raw Gray/Bayer data rather than native YUV.

## Metadata resolution

When compatible metadata exists, PixelScope resolves the interpretation before asking you. The current precedence is:

1. PixelScope same-stem `.json` profile.
2. Compatible same-stem `.imgprops` metadata.
3. RAW profile dialog when required.

An `.imgprops` file can provide dimensions, sensor bit width, Bayer/Gray image type, Bayer pattern, and pedestal information. Missing byte-layout information is not guessed from unrelated fields; compatible defaults follow the current RAW contract.

## RAW profile fields

- **Width / Height**: decoded pixel dimensions.
- **Bit depth**: meaningful source bits per pixel sample.
- **Storage/container**: unpacked `uint8`, unpacked `uint16`, generic packed bitstream, or packed MIPI RAW10/12/14.
- **Byte order**: little- or big-endian for `uint16` storage.
- **Bit alignment**: LSB/MSB alignment for sub-16-bit samples stored in `uint16`.
- **Bit order**: MSB-first or LSB-first sample-bit order for generic packed bitstreams.
- **Stride**: bytes from the start of one stored row to the next. It can be larger than the minimum packed row size because of row padding.
- **Offset**: bytes before the first image row.
- **Layout**: Gray or Bayer.
- **Bayer pattern**: RGGB, GRBG, GBRG, or BGGR for Bayer input.
- **Black/white level**: source interpretation levels used by applicable display/analysis contracts.

## Generic packed bitstream

**Packed bitstream** stores each row as consecutive fixed-width pixel codes without a `uint8`/`uint16` sample container. PixelScope supports 1-16 meaningful bits per sample and decodes the result into the normal native integer source domain.

For one row, the valid payload is:

`ceil(width × bit_depth / 8)` bytes.

The bitstream restarts at the first byte of every row. **MSB first** means pixel 0's most-significant bit is the first stream bit; **LSB first** means pixel 0's least-significant bit is first. When a row does not end on a byte boundary, unused bits at the end of the final payload byte are ignored.

The stored row may be larger than the valid payload. The remaining `stride - payload` bytes are row padding and are skipped during decode. When a source file is selected and `(file_size - offset)` is exactly divisible by height, the dialog can infer:

`stride = (file_size - offset) / height`.

For example, a 4000×2252, 10-bit file of 11,278,016 bytes has a 5008-byte row stride. The valid pixel payload is 5000 bytes, so PixelScope decodes 5000 bytes and skips 8 padding bytes on every row.

## MIPI RAW10/12/14

Packed MIPI formats have exact bit-depth/storage relationships: RAW10 is 10-bit, RAW12 is 12-bit, and RAW14 is 14-bit. The packed group geometry also constrains width: RAW10 and RAW14 require widths compatible with four-pixel groups, while RAW12 requires two-pixel groups.

For tightly packed rows, the minimum row byte counts are `width × 5/4` for RAW10, `width × 3/2` for RAW12, and `width × 7/4` for RAW14. If the file uses padded rows, enter the actual larger stride.

## Size validation

PixelScope validates that the file contains enough payload for the selected offset, stride, height, and packing. Common failures are wrong dimensions, wrong storage format, stride smaller than the packed row size, truncated data, and an incorrect offset.

## Example: opening RAW14

1. Open the `.raw`/`.data` source.
2. If no valid sidecar resolves it, use the RAW profile dialog.
3. Enter Width and Height.
4. Set Bit depth to **14** and storage to **MIPI RAW14**.
5. Choose Gray or Bayer and, for Bayer, the correct CFA pattern.
6. Enter the real row stride and offset if the file is not tightly packed from byte zero.
7. Confirm only after the expected payload geometry matches the file.

## Troubleshooting keywords

**packed bitstream**, **bit order**, **RAW14**, **MIPI**, **stride**, **offset**, **LSB**, **MSB**, **little endian**, **big endian**, **Bayer pattern**, **file size**, **sidecar**, **imgprops**.
