# PixelScope synthetic bit-depth variations

Extract or copy this folder to:

    manual/bit_depth_variations

The same deterministic FHD grayscale scene is quantized to 8, 10, 12, 14,
and 16 bits. Each `.raw` file has a same-stem `.json` RawProfile sidecar.

Storage:
- 8-bit: unpacked uint8
- 10/12/14/16-bit: unpacked uint16 little-endian
- Resolution: 1920 x 1080
- Channel layout: GRAY
- Black level: 0
- White level: `(1 << bit_depth) - 1`

The bottom-right 256 x 256 patch guarantees complete native code coverage.

Expected Histogram Auto bins:
- 8-bit: 256
- 10-bit: 1024
- 12-bit: 4096
- 14-bit: 4096
- 16-bit: 4096

These are unpacked RAW fixtures, not MIPI-packed RAW10/12/14 files.
